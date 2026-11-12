"""Recover saved family-specific clauses, not source/gold lookup values."""
import re
from prepare_audit import OUT,read,save,sha

DEST=OUT/'saved_sulfide_ether_methods_recovery'
PATS={
 'methyl':re.compile(r'(?P<material>Vinyl methyl sulfide) on (?P<action>slow polymerization) for (?P<duration>several months) in a (?P<vessel>sealed tube) under (?P<illumination>fluorescent light) gave a (?P<output_state>solid material)'),
 'bulk':re.compile(r'(?P<material_a>Vinyl ethyl sulfide) and (?P<material_b>vinyl n-butyl sulfide) were (?P<action>bulk polymerized) with (?P<initiator>azobisisobutyronitrile) at\s+\$(?P<temperature>\d+)\^\{\\circ\}\$\s*C\. in a (?P<vessel>sealed tube) to give (?P<output_state>viscous liquids)'),
 'crosslink':re.compile(r'(?P<input_state>these liquids) were (?P<action>crosslinked) with (?P<dcp>\d+)(?P<dcp_unit>% by weight) of (?P<crosslinker>dicumyl peroxide) and (?P<sulfur>\d+)(?P<sulfur_unit>% by weight) of (?P<sulfur_form>finely divided sulfur) in a (?P<vessel>sealed tube) at\s+\$(?P<temperature>\d+)\^\{\\circ\}\$\s*C\.'),
 'posttreatment':re.compile(r'The (?P<input_state>crosslinked materials) were (?P<extraction>extracted) with (?P<solvent>benzene) and finally (?P<drying>dried) at\s+\$(?P<temperature>\d+)\^\{\\circ\}\$\s*C\. and (?P<pressure>\d+) (?P<pressure_unit>mm\. pressure) for (?P<duration>\d+) (?P<duration_unit>hrs\.)'),
 'ether_molding':re.compile(r'For ease of handling of the polymers of (?P<material_a>vinyl n-octyl), (?P<material_b>vinyl n-decyl) and (?P<material_c>vinyl n-dodecyl) ethers they were (?P<state>lightly crosslinked) with (?P<dcp>\d+) (?P<dcp_unit>wt\.-%) of (?P<crosslinker>dicumyl peroxide) at (?P<temperature>\d+)(?P<temperature_unit>°C)\. in a (?P<mold>suitable rectangular mold) (?P<pressure>under pressure)\.')}


def main():
 rows=[]
 for p in read(OUT/'existing_evidence_recovery_inputs/manifest.json')['papers']:
  assert sha(p['path'])==p['sha256'];cache=read(p['path']);path=OUT/'candidate_v10'/(p['reference_no']+'.json');pred=read(path);ns='native_process_context' if 'native_process_context' in pred else 'native_process_supplement';native=pred.get(ns,{});fragments={};proposals=[]
  for name,pattern in PATS.items():
   matches=[(q,m) for q in cache['source_quotations'] if (m:=pattern.search(q['text']))]
   if len(matches)!=1:break
   q,m=matches[0];fragments[name]=dict(existing_quote=q,captures={k:dict(value_raw=v,original_quote_span=list(m.span(k))) for k,v in m.groupdict().items()})
  if len(fragments)==5:
   steps=native.get('process_steps',[]);bulk=[(i,s) for i,s in enumerate(steps) if s.get('process_type')=='polymerization' and s.get('parameters',{}).get('initiator')==fragments['bulk']['captures']['initiator']['value_raw']]
   ether=[(i,s) for i,s in enumerate(steps) if s.get('process_type')=='crosslinking' and any('n-octyl' in t.get('polymer_name','') and 'n-decyl' in t.get('polymer_name','') and 'n-dodecyl' in t.get('polymer_name','') for t in native['samples'] if t['sample_id'] in s['output_sample_ids'])]
   if len(bulk)==len(ether)==1:
    locators=[{(o['source_path'],o['original_evidence_metadata'].get('block_id')) for o in fragments[name]['existing_quote']['occurrences']} for name in ['methyl','bulk','crosslink','posttreatment']];common=set.intersection(*locators)
    if common:
     bi,bs=bulk[0];ei,es=ether[0];proposals=[dict(proposal_id='separate_saved_sulfide_methods_and_ether_mold',fragments=fragments,existing_bulk_method=dict(path=f'/{ns}/process_steps/{bi}',original_step=bs),existing_ether_method=dict(path=f'/{ns}/process_steps/{ei}',original_step=es),existing_sulfide_sample_targets=[dict(path=f'/{ns}/samples/{i}',sample_id=s['sample_id']) for i,s in enumerate(native['samples']) if s['sample_id'] in bs['output_sample_ids']],existing_ether_sample_targets=[dict(path=f'/{ns}/samples/{i}',sample_id=s['sample_id']) for i,s in enumerate(native['samples']) if s['sample_id'] in es['output_sample_ids']],saved_bulk_method_scope_requires_source_approval=True,material_names_are_separate_method_instances_not_a_pooled_batch=True,shared_saved_source_locators=[dict(source_path=p,block_id=b) for p,b in sorted(common)])]
  dest=DEST/'papers'/(p['reference_no']+'.json');save(dest,dict(reference_no=p['reference_no'],cache_path=p['path'],cache_sha256=p['sha256'],candidate_source=dict(path=str(path),sha256=sha(path)),proposals=proposals,accepted_into_prediction=False,reference_files_or_scores_used_as_generator_inputs=False,reference_seen_previously_during_error_diagnosis=True,pdf_or_stage0_source_read_by_generator=False,property_outputs_modified=False,external_api_calls=0));rows.append(dict(reference_no=p['reference_no'],path=str(dest),sha256=sha(dest),proposals=len(proposals)))
 result=dict(papers=rows,papers_scanned=len(rows),groups=sum(p['proposals'] for p in rows),generator_code_sha256=sha(__file__),reference_files_or_scores_used_as_generator_inputs=False,reference_seen_previously_during_error_diagnosis=True,pdf_or_stage0_source_read_by_generator=False,external_api_calls=0);save(DEST/'manifest.json',result);print({'scanned':len(rows),'groups':result['groups'],'papers':[p['reference_no'] for p in rows if p['proposals']]})

if __name__=='__main__':main()
