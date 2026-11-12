"""Recover literal bottle and crystallization methods from saved evidence only.

Scans all 101 frozen packets. No references, scores, PDFs or full text are read.
No original native product list is assumed to share the stated VCl3 recipe.
"""
import re
from prepare_audit import OUT,read,save,sha,canonical

DEST=OUT/'saved_bottle_and_crystallization'
PURGE=re.compile(r'A (?P<volume>\d+-ml\.) pressure bottle was flushed with (?P<gas>dry nitrogen) and charged with (?P<monomer_amount>\d+(?:\.\d+)? mole) of monomer and (?P<v_amount>\d+(?:\.\d+)? mole) of (?P<v_identity>anhydrous VCl₃)',re.I)
INJECT=re.compile(r'The bottle was capped with a (?P<cap>neoprene-lined self-sealing cap) and (?P<al_amount>\d+(?:\.\d+)? mole) of (?P<al_identity>Al\(C₂H₅\)₃) was injected by means of a (?P<injector>hypodermic syringe)',re.I)
REACT=re.compile(r'The bottle was placed inside a (?P<cage>metal cage) and (?P<agitation>tumbled) for (?P<duration>\d+(?:\.\d+)? hr\.) at (?P<temperature>\d+(?:\.\d+)?°C\.) in a (?P<bath>water bath)',re.I)
CRYST=re.compile(r'Polymers were crystallized by heating in a (?P<apparatus>hot Soxhlet extractor) with (?P<medium>boiling acetone) for (?P<duration>\d+(?:\.\d+)? hr\.)',re.I)
AFTER=re.compile(r'They were then (?P<filter>filtered) and dried for (?P<duration>\d+(?:\.\d+)? hr\.) at (?P<temperature>\d+(?:\.\d+)?°C\.) (?P<pressure>under vacuum)',re.I)
DRY=re.compile(r'The polymer was dried at\s+(?P<temperature>\$\d+(?:\.\d+)?\^\{\\circ\}\$\s*C\.) in a (?P<equipment>vacuum oven)',re.I)


def capture(q,m):
 return dict(existing_quote=q,matched_quote_span=list(m.span()),captures={k:dict(value_raw=v,original_quote_span=list(m.span(k))) for k,v in m.groupdict().items()})


def main():
 rows=[];freeze=OUT/'candidate_v10/freeze.json'
 for p in read(freeze)['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];doc=read(p['candidate_path']);origin=doc['property_source'];assert sha(origin['path'])==origin['sha256']
  cp=OUT/'existing_evidence_recovery_inputs/papers'/(p['reference_no']+'.json');cache=read(cp);byblock={}
  for q in cache['source_quotations']:
   for o in q['occurrences']:
    if o['source_path']!=origin['path']:continue
    block=o['original_evidence_metadata'].get('block_id')
    if block:byblock.setdefault(block,{})[q['text_sha256']]=q
  proposals=[];has_polymerization=any(s.get('process_type')=='polymerization' for ns in ['native_process_context','native_process_supplement'] for s in doc.get(ns,{}).get('process_steps',[]))
  if has_polymerization:
   for block,quotes in byblock.items():
    for q in quotes.values():
     a,b,c=PURGE.search(q['text']),INJECT.search(q['text']),REACT.search(q['text'])
     if not(a and b and c) or not(a.end()<b.start()<c.start()):continue
     proposals.append(dict(proposal_id='BOTTLE_'+str(len(proposals)+1),method='source_local_vcl3_bottle_recipe',source_block_id=block,
      fragments={'charge':capture(q,a),'initiation':capture(q,b),'reaction':capture(q,c)},
      native_output_list_not_inherited=True,no_solvent_absence_claim=True,actual_phase_conversion_and_crystallinity_unknown=True))
   for block,quotes in byblock.items():
    pairs=[]
    for q in quotes.values():
     a=CRYST.search(q['text'])
     if not a:continue
     for r in quotes.values():
      b=AFTER.search(r['text'])
      if b:pairs.append((q,a,r,b))
    if len(pairs)==1:
     q,a,r,b=pairs[0];proposals.append(dict(proposal_id='CRYST_'+str(len(proposals)+1),method='source_local_crystallization_conditioning',source_block_id=block,
      fragments={'heat':capture(q,a),'post':capture(r,b)},all_identities_not_assumed_to_crystallize=True,not_purification_soxhlet=True))
   for block,quotes in byblock.items():
    for q in quotes.values():
     m=DRY.search(q['text'])
     if m:proposals.append(dict(proposal_id='DRY_'+str(len(proposals)+1),method='source_local_polymer_oven_drying',source_block_id=block,
      fragments={'dry':capture(q,m)},duration_unknown=True,no_link_to_crystallization_or_individual_native_output=True))
  target=DEST/'papers'/(p['reference_no']+'.json');save(target,dict(reference_no=p['reference_no'],candidate_input=p,property_source=origin,
   cache_path=str(cp),cache_sha256=sha(cp),proposals=proposals,accepted_into_prediction=False,reference_or_pdf_source_inputs=False,external_api_calls=0))
  rows.append(dict(reference_no=p['reference_no'],path=str(target),sha256=sha(target),proposals=len(proposals)))
 save(DEST/'manifest.json',dict(papers_scanned=len(rows),proposal_groups=sum(x['proposals'] for x in rows),papers=rows,
  generator_code_sha256=sha(__file__),baseline_freeze_sha256=sha(freeze),accepted_predictions=0,reference_or_pdf_source_inputs=False,external_api_calls=0))
 print({'scanned':len(rows),'groups':sum(x['proposals'] for x in rows),'papers_with_groups':sum(bool(x['proposals']) for x in rows)})


if __name__=='__main__':main()
