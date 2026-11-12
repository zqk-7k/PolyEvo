"""Recover a specifically scoped Q protocol from saved quotations only.

No PDF, reference, source full text or scoring file is opened. Every numerical
value is a literal span in a frozen prediction's evidence register. All fragments
must have the same original property document and source block. A unique existing
Q specimen and unique swelling characterization are mandatory. No time points,
surface-drying event, solvent name or quantitative percent basis is invented.
"""
from prepare_audit import OUT,read,save,sha,canonical
from inspect_fixed_pair import resolve
import re

DEST=OUT/'saved_q_swelling_protocol'
SELECT=re.compile(r'For the estimation of swelling coefficient\s*\[Q\],\s*a vulcanizate containing\s+(?P<loading>\d+(?:\.\d+)?\s+phr)\s+(?P<agent>DICUP)\s+and vulcanized for\s+(?P<cure_time>\d+(?:\.\d+)?\s+min)\s+at\s+(?P<cure_temperature>\d+(?:\.\d+)?\s*±\s*\d+(?:\.\d+)?\s*°C)\s+was used',re.I)
SWELL=re.compile(r'samples were allowed to swell in\s+(?P<solvent_scope>different solvents)\s+containing\s+(?P<antioxidant_fraction>\d+(?:\.\d+)?%)\s+(?P<antioxidant>phenyl-[βß]-naphthyl amine)\s+at\s+(?P<temperature>\d+(?:\.\d+)?\s*±\s*\d+(?:\.\d+)?\s*°C)',re.I)
EQUIL=re.compile(r'The\s+(?P<duration>\d+(?:\.\d+)?\s+hrs)\s+period was found to be\s+(?P<observation>sufficient for the attainment of swelling equilibrium)',re.I)
DRY=re.compile(r'Samples were dried in\s+(?P<equipment>air oven)\s+for\s+(?P<duration>\d+(?:\.\d+)?\s+hrs)\s+at\s+(?P<temperature>\d+(?:\.\d+)?\s*°C),\s*then\s+(?P<vacuum>i\.vac\.)\s+and were finally weighed',re.I)


def numbers(text):return re.findall(r'(?<![\d.])[−-]?\d+(?:\.\d+)?',text)


def main():
 frozen=OUT/'candidate_v10/freeze.json';papers=[]
 for p in read(frozen)['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];doc=read(p['candidate_path']);origin=doc['property_source'];assert sha(origin['path'])==origin['sha256'];prop=read(origin['path'])
  cache_path=OUT/'existing_evidence_recovery_inputs/papers'/(p['reference_no']+'.json');cache=read(cache_path)
  byblock={}
  for q in cache['source_quotations']:
   for o in q['occurrences']:
    if o['source_path']!=origin['path']:continue
    block=o['original_evidence_metadata'].get('block_id')
    if block:byblock.setdefault(block,{})[q['text_sha256']]=q
  rows=[]
  for block,quotes in byblock.items():
   slots={}
   for name,pattern in [('selection',SELECT),('swelling',SWELL),('equilibrium',EQUIL),('drying',DRY)]:
    matches=[]
    for q in quotes.values():
     m=pattern.search(q['text'])
     if m:matches.append((len(q['text']),q,m))
    if not matches:break
    _,q,m=max(matches,key=lambda x:x[0]);slots[name]=(q,m)
   if len(slots)!=4:continue
   candidates=[]
   for ns in ['native_process_context','native_process_supplement']:
    ctx=doc.get(ns,{})
    for si,s in enumerate(ctx.get('samples',[])):
     if s.get('sample_kind')!='test_specimen':continue
     purposes=' '.join(s.get('intended_use',[]));history=s.get('state_description','')
     if not re.search(r'swelling coefficient\s*\[?Q\]?',purposes,re.I) or 'central portion' not in history.lower():continue
     for ci,c in enumerate(prop.get('characterizations',[])):
      if c.get('method_normalized','').lower()!='swelling' or 'swelling coefficient' not in c.get('method_raw','').lower():continue
      if s.get('refers_to_entity')!=c.get('entity_id') or not s.get('refers_to_entity'):continue
      durations=[v for k,v in c.get('parameters',{}).items() if 'time' in k.lower() and isinstance(v,str)]
      if not any(numbers(v)==numbers(slots['equilibrium'][1].group('duration')) for v in durations):continue
      temp=c.get('measurement_context',{}).get('temperature',{}).get('raw','')
      if numbers(temp)!=numbers(slots['swelling'][1].group('temperature')):continue
      producer=[(j,step) for j,step in enumerate(ctx.get('process_steps',[])) if step.get('output_sample_ids')==[s['sample_id']] and step.get('process_type')=='specimen_preparation']
      if len(producer)!=1:continue
      candidates.append((ns,si,s,ci,c,producer[0]))
   if len(candidates)!=1:continue
   ns,si,s,ci,c,(stepi,step)=candidates[0]
   captured={}
   for name,(q,m) in slots.items():
    captures={}
    for key,value in m.groupdict().items():
     a,b=m.span(key);assert q['text'][a:b]==value
     captures[key]=dict(value_raw=value,original_quote_span=[a,b])
    captured[name]=dict(existing_quote=q,captures=captures)
   rows.append(dict(proposal_id=f'Q.{len(rows)+1:03}',native_namespace=ns,
    specimen_path=f'/{ns}/samples/{si}',specimen_sha256=canonical(s),
    specimen_producer_path=f'/{ns}/process_steps/{stepi}',specimen_producer_sha256=canonical(step),
    specimen_sample_id=s['sample_id'],entity_id=s['refers_to_entity'],
    characterization_path=f'/characterizations/{ci}',characterization_sha256=canonical(c),
    original_common_source_block_id=block,captured_fragments=captured,
    separate_solvent_applications_not_physical_mixture=True,
    observation_time_points_not_recovered=[],surface_drying_not_recovered=True,
    percent_basis_unspecified=True,source_scope_and_anaphora_review_required=True,
    accepted_into_prediction=False,reference_or_pdf_source_inputs=False))
  target=DEST/'papers'/(p['reference_no']+'.json');save(target,dict(reference_no=p['reference_no'],candidate_input=p,property_source=origin,
   cache_path=str(cache_path),cache_sha256=sha(cache_path),proposals=rows,external_api_calls=0))
  papers.append(dict(reference_no=p['reference_no'],path=str(target),sha256=sha(target),proposals=len(rows)))
 save(DEST/'manifest.json',dict(papers_scanned=len(papers),proposal_groups=sum(x['proposals'] for x in papers),
  generator_code_sha256=sha(__file__),baseline_freeze_sha256=sha(frozen),
  reference_or_pdf_source_inputs=False,new_pdf_information=0,accepted_predictions=0,papers=papers,external_api_calls=0))
 print({'papers_scanned':len(papers),'proposal_groups':sum(x['proposals'] for x in papers),'accepted_predictions':0})


if __name__=='__main__':main()
