"""Freeze inputs, prepare source-only reference audit packets, no predictions generated."""
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parent
C=ROOT/'1014_101篇工艺与关系_无API持续进化/coordinator'
N=C/'property_native_start'
W=ROOT/'archives/process101'
KINDS=('operation','parameter','order','binding','state')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def canonical(d):return hashlib.sha256(json.dumps(d,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def clean_fact(d):
    if isinstance(d,dict): return {k:clean_fact(v) for k,v in d.items() if k not in ('source','source_block_ids','source_evidence','quote','pdf_page','evidence')}
    if isinstance(d,list): return [clean_fact(v) for v in d]
    return d
def flatten(d):
    spec=importlib.util.spec_from_file_location('facts_only',C.parent/'build/process_scoring.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m.facts(d)

def main():
    inventory=read(C/'paper_inventory.json'); assert len(inventory)==101
    ids=[x['reference_no'] for x in inventory]; assert len(set(ids))==101
    original=read(N/'input_freeze.json');files=[]
    for x in original['files']:
        p=Path(x['snapshot']);actual=sha(p)
        if actual!=x['sha256']: raise ValueError('Original input changed: '+str(p))
        files.append({'path':str(p),'sha256':actual,'role':'immutable_native_snapshot'})
    for p in [C/'paper_inventory.json',C/'protocol.json',C/'property_evaluation_baseline/metrics.json',
              C/'property_evaluation_baseline/freeze.json',C/'references/process31_v2.json']:
        files.append({'path':str(p),'sha256':sha(p),'role':'inventory_or_baseline'})
    legacy_inputs=ROOT/'1015_已有101篇输出_直接核查/process_review/inputs'
    ref_manifest=[];source_manifest=[];packet_counts=Counter()
    for row in inventory:
        ref=row['reference_no'];batch=row['batch'];srcpath=N/ref/'stage0_blocks.json';native=read(srcpath)
        source_manifest.append({'reference_no':ref,'path':str(srcpath),'sha256':sha(srcpath),
                                'page_indexing':'zero_based_native','elements':len(native['elements'])})
        if batch=='B0':
            p=C/'references/flat31'/f'{ref}.json';facts=read(p)['facts'];status='prior_reference_review'
        elif batch in ('B1','B2'):
            p=C/f'references/{batch}_verified_frozen/papers'/ref/'reference.json';facts=flatten(read(p));status='prior_reference_review'
        else:
            p=C/'references/drafts70'/ref/'source_resolved.json'
            if not p.exists():p=C/'references/drafts70'/ref/'source_draft.json'
            doc=read(p);facts=flatten(doc);status='pending_semantic_review'
            source_path=W/f'reference_{batch}_independent_verification/inputs'/ref/'source.json'
            source=read(source_path)
            # Only source and reference draft are included. Never include predictions or scores.
            packet={'reference_no':ref,'batch':batch,'reference_path':str(p),'reference_sha256':sha(p),
                    'source_path':str(source_path),'source_sha256':sha(source_path),
                    'facts':facts,'source':source,'scope':doc.get('scope'),
                    'source_issues':doc.get('source_conflicts',[]),'excluded_or_pending':doc.get('excluded_or_pending',[]),
                    'predictions_included':False,'semantic_review_complete':False,'expert_gold':False}
            save(OUT/'reference_packets'/f'{ref}.json',packet)
            packet_counts.update(f['kind'] for f in facts)
            files.append({'path':str(source_path),'sha256':sha(source_path),'role':'source_only_reference_audit_source'})
        fids=[f['id'] for f in facts];assert len(fids)==len(set(fids)),ref
        facts_digest=canonical([clean_fact(f) for f in facts])
        old=read(legacy_inputs/f'{ref}.json')
        if status=='prior_reference_review':
            old_digest=canonical([clean_fact(f) for f in old['reference_facts'] if f['kind']!='state'])
            assert facts_digest==old_digest,(ref,'Reference scope or fact changed')
        save(OUT/'reference_pool'/f'{ref}.json',{'reference_no':ref,'facts':facts,'status':status,
             'frozen_for_scoring':status=='prior_reference_review','source_reference_path':str(p),'source_reference_sha256':sha(p)})
        ref_manifest.append({'reference_no':ref,'batch':batch,'path':str(p),'sha256':sha(p),
                             'canonical_facts_sha256':facts_digest,'status':status,'counts':dict(Counter(f['kind'] for f in facts))})
        files.append({'path':str(p),'sha256':sha(p),'role':'fixed_reference_or_pending_draft'})
    save(OUT/'input_freeze.json',{'paper_count':101,'files':files,'paper_ids':ids,'external_api_calls':0,
         'old_outputs_modified':False,'test20_outputs_or_scores_read':False,'reference_papers_ready':51,
         'reference_papers_pending':50,'material_state_reference_scope':'pending_source_only_extension'})
    save(OUT/'reference_inventory.json',ref_manifest);save(OUT/'source_inventory.json',source_manifest)
    print(json.dumps({'papers':len(ids),'verified_snapshot_files':len(original['files']),
                     'reference_packets':50,'pending_reference_facts':dict(packet_counts),
                     'property_baseline':read(C/'property_evaluation_baseline/metrics.json')},ensure_ascii=False))

if __name__=='__main__':main()
