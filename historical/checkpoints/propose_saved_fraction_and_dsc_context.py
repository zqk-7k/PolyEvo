"""Scan saved evidence, never reference answers, full source files or scores.

These are source-literal proposals, not accepted predictions or reference hits.
"""
import re
from prepare_audit import OUT,read,save,sha

DEST=OUT/'saved_fraction_and_dsc_context'
FRACTION=re.compile(r'The (?P<fraction>soluble fraction) was (?P<extract>extracted) with (?P<solvent>CHCl₃) and then (?P<precip>reprecipitated) from (?P<medium>methanol)\. This fraction of the polymer was used for (?P<uses>GPC and spectral measurements as well as film casting)\.')
DSC=re.compile(r'Differential scanning calorimetry \(DSC\) traces of (?P<identity>BDSDA–PDA) film samples.*?DSC curve 1 \(obtained on (?P<initial>crystalline BDSDA–PDA film).*?After (?P<quench>melting and quenching in liquid nitrogen), the polymer film had become (?P<amorphous>amorphous) \(curve 2\).*?and a (?P<partial>partial melt near\s+\$400\^\{\\circ\}\$ C)\. Upon (?P<cool>cooling the same sample at\s+\$1\^\{\\circ\}\$ C/min), the (?P<after>amorphous film).*?with (?P<no_melt>no melt)\.',re.S)


def main():
 rows=[]
 for p in read(OUT/'candidate_v10/freeze.json')['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];pred=read(p['candidate_path']);origin=pred['property_source'];assert sha(origin['path'])==origin['sha256']
  cp=OUT/'existing_evidence_recovery_inputs/papers'/(p['reference_no']+'.json');cache=read(cp);proposals=[]
  for q in cache['source_quotations']:
   occ=[o for o in q['occurrences'] if o['source_path']==origin['path']]
   if not occ:continue
   for method,pattern in [('soluble_fraction_workup',FRACTION),('successive_dsc_states',DSC)]:
    m=pattern.search(q['text'])
    if not m:continue
    if method=='soluble_fraction_workup':
     ss=pred.get('native_process_context',{}).get('samples',[]);names=sorted({x.get('polymer_name') for x in ss if x.get('polymer_name') in ['PBTOMe','PBTH','PBTCl','PBTBr','PBTCN']})
     if len(names)!=5:continue
     anchors=[dict(path='/native_process_context/samples/'+str(i),sample_id=s['sample_id']) for i,s in enumerate(ss) if s.get('sample_id') in ['s001','s002','s003','s004','s005'] and s.get('polymer_name') in names]
    else:
     ss=pred.get('native_process_context',{}).get('samples',[]);matches=[(i,s) for i,s in enumerate(ss) if 'amorphous (DSC curve 2)' in s.get('state_description','') and s.get('polymer_name')=='BDSDA-PDA']
     if len(matches)!=1:continue
     i,s=matches[0];anchors=[dict(path='/native_process_context/samples/'+str(i),sample_id=s['sample_id'],role='after_liquid_nitrogen_quench')]
     initial=[(j,t) for j,t in enumerate(ss) if t.get('polymer_name')=='BDSDA-PDA' and '300' in t.get('state_description','') and t.get('intended_use')==['DSC measurement']]
     if len(initial)!=1:continue
     j,t=initial[0];anchors.append(dict(path='/native_process_context/samples/'+str(j),sample_id=t['sample_id'],role='initial_cured_DSC_specimen'));names=['BDSDA–PDA']
    proposals.append(dict(proposal_id=method+'_'+str(len(proposals)+1),method=method,existing_quote=q,
     original_common_source_block_ids=sorted({o['original_evidence_metadata']['block_id'] for o in occ if o['original_evidence_metadata'].get('block_id')}),
     matched_quote_span=list(m.span()),captures={k:dict(value_raw=v,original_quote_span=list(m.span(k))) for k,v in m.groupdict().items()},
     existing_identity_anchors=anchors,source_local_identity_names=names,physical_batch_identity_not_inferred=True))
  target=DEST/'papers'/(p['reference_no']+'.json');save(target,dict(reference_no=p['reference_no'],candidate_input=p,property_source=origin,
   cache_path=str(cp),cache_sha256=sha(cp),proposals=proposals,accepted_into_prediction=False,reference_or_pdf_source_inputs=False,external_api_calls=0))
  rows.append(dict(reference_no=p['reference_no'],path=str(target),sha256=sha(target),proposals=len(proposals)))
 save(DEST/'manifest.json',dict(papers_scanned=len(rows),proposal_groups=sum(x['proposals'] for x in rows),papers=rows,generator_code_sha256=sha(__file__),
  baseline_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),accepted_predictions=0,reference_or_pdf_source_inputs=False,external_api_calls=0))
 print({'scanned':len(rows),'groups':sum(x['proposals'] for x in rows),'papers_with_groups':sum(bool(x['proposals']) for x in rows)})


if __name__=='__main__':main()
