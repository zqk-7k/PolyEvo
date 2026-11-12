"""Source-only recovery of two missing conditions in an existing PAA method.

Reads frozen predictions and their saved quotations only. Does not read PDF,
full text, reference answers, semantic judgments, scores or other trials.
The two quotations must come from the same original property document/block.
"""
import re
from prepare_audit import OUT,read,save,sha,canonical

DEST=OUT/'saved_paa_method_context'
MIX=re.compile(r'Poly\(amic acids\) were synthesized by mixing (?P<ratio>equimolar amounts of diamine and dianhydride) at (?P<concentration>\d+% solids \(w/w\)) in (?P<solvent>DMAc)',re.I)
CAST=re.compile(r'Films of the poly\(amic acid\) solutions were cast on (?P<substrate>plate glass) by using an (?P<gap>\d+-mil) doctor blade gap',re.I)


def main():
 rows=[];freeze=OUT/'candidate_v10/freeze.json'
 for p in read(freeze)['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];doc=read(p['candidate_path']);origin=doc['property_source']
  assert sha(origin['path'])==origin['sha256']
  cache_path=OUT/'existing_evidence_recovery_inputs/papers'/(p['reference_no']+'.json');cache=read(cache_path);byblock={}
  for q in cache['source_quotations']:
   for o in q['occurrences']:
    if o['source_path']!=origin['path']:continue
    block=o['original_evidence_metadata'].get('block_id')
    if block:byblock.setdefault(block,{})[q['text_sha256']]=q
  proposals=[]
  for ns in ['native_process_context','native_process_supplement']:
   ctx=doc.get(ns,{});samples={x['sample_id']:(i,x) for i,x in enumerate(ctx.get('samples',[]))};pairs=[]
   for i,step in enumerate(ctx.get('process_steps',[])):
    if step.get('process_type')!='polymerization' or len(step.get('output_sample_ids',[]))<2:continue
    outputs=step['output_sample_ids']
    if any(s not in samples or samples[s][1].get('state_description','').lower()!='poly(amic acid)' for s in outputs):continue
    if step.get('parameters',{}).get('solids content')!='15% (w/w)' or step.get('parameters',{}).get('solvent')!='DMAc':continue
    for j,cast in enumerate(ctx['process_steps']):
     if cast.get('process_type')!='casting' or set(cast.get('input_sample_ids',[]))!=set(outputs):continue
     if cast.get('parameters',{}).get('doctor blade gap')!='18-mil':continue
     if any(s not in samples or 'poly(amic acid) film' not in samples[s][1].get('state_description','').lower() for s in cast.get('output_sample_ids',[])):continue
     pairs.append((i,step,j,cast))
   if len(pairs)!=1:continue
   i,step,j,cast=pairs[0]
   for block,quotes in byblock.items():
    matches={}
    for key,regex in [('polymerization',MIX),('casting',CAST)]:
     found=[(len(q['text']),q,regex.search(q['text'])) for q in quotes.values() if regex.search(q['text'])]
     if not found:break
     _,q,m=max(found,key=lambda a:a[0]);matches[key]=dict(existing_quote=q,
      captures={k:dict(value_raw=v,original_quote_span=list(m.span(k))) for k,v in m.groupdict().items()})
    if len(matches)!=2:continue
    proposals.append(dict(proposal_id='PAA_CONTEXT',native_namespace=ns,
     existing_polymerization_path=f'/{ns}/process_steps/{i}',existing_polymerization_sha256=canonical(step),
     existing_casting_path=f'/{ns}/process_steps/{j}',existing_casting_sha256=canonical(cast),
     original_common_source_block_id=block,captured_fragments=matches,
     new_conditions=['literal equimolar diamine/dianhydride ratio','plate glass casting substrate'],
     sample_pairing_from_existing_input_output_not_array_positions=True,
     precursor_identities_or_unreported_conversion_not_generated=True,accepted_into_prediction=False))
  dest=DEST/'papers'/(p['reference_no']+'.json');save(dest,dict(reference_no=p['reference_no'],candidate_input=p,
   property_source=origin,cache_path=str(cache_path),cache_sha256=sha(cache_path),proposals=proposals,
   reference_or_pdf_source_inputs=False,external_api_calls=0))
  rows.append(dict(reference_no=p['reference_no'],path=str(dest),sha256=sha(dest),proposals=len(proposals)))
 save(DEST/'manifest.json',dict(papers_scanned=len(rows),proposal_groups=sum(x['proposals'] for x in rows),papers=rows,
  generator_code_sha256=sha(__file__),baseline_freeze_sha256=sha(freeze),reference_or_pdf_source_inputs=False,
  accepted_predictions=0,external_api_calls=0))
 print({'scanned':len(rows),'proposal_groups':sum(x['proposals'] for x in rows),'accepted_predictions':0})


if __name__=='__main__':main()
