"""Proposal generation uses frozen predictions and their saved evidence only."""
import re
from copy import deepcopy
from prepare_audit import OUT,read,save,sha,canonical

DEST=OUT/'saved_polyester_scope_repair'
ACETYL=re.compile(r'The (?P<group>hydroxyl end-groups) were measured by (?P<method>acetylation) with (?P<reagent>pyridine/acetic anhydride reagent)')
MINIMUM=re.compile(r'all the (?P<scope>polymers used) had (?P<quantity>molecular weights) of (?P<relation>at least) (?P<minimum>10,000)')


def capture(q,m):return dict(existing_quote=q,matched_quote_span=list(m.span()),captures={k:dict(value_raw=v,original_quote_span=list(m.span(k))) for k,v in m.groupdict().items()})


def main():
 rows=[]
 for p in read(OUT/'candidate_v10/freeze.json')['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];pred=read(p['candidate_path']);cp=OUT/'existing_evidence_recovery_inputs/papers'/(p['reference_no']+'.json');cache=read(cp);pg=pred.get('process_graph',{});proposals=[]
  patch=[]
  for i,op in enumerate(pg.get('operations',[])):
   scope=op.get('applies_to',[])
   if not any('acid–glycol route:' in t for t in scope):continue
   exclusions=[b for b in pg.get('bindings',[]) if b.get('operation_id')==op['id'] and 'excludes ester-route' in b.get('description','')]
   if not exclusions:continue
   for j,par in enumerate(op.get('parameters',[])):
    child=par.get('applies_to',[])
    if not any('n=0,1,2,3' in t or 'n-alkylmalonates' in t for t in child):continue
    # A child cannot extend the explicitly excluded parent route.
    patch.append(dict(path=f'/process_graph/operations/{i}/parameters/{j}/applies_to',before=deepcopy(child),after=deepcopy(scope),
     parent_operation_path=f'/process_graph/operations/{i}',operation_id=op['id'],parameter_index=j,
     explicit_parent_exclusion_binding_ids=[b['id'] for b in exclusions],value_and_role_unchanged=True))
  if patch:
   acid=[q for q in cache['source_quotations'] if all(t in q['text'] for t in ['dibasic acids','oxygen-free','1 mmHg','5,000','10,000'])]
   ester=[q for q in cache['source_quotations'] if all(t in q['text'] for t in ['diethyl esters','150','reduced pressure','zinc acetate'])]
   if len(acid)==1 and len(ester)==1:
    proposals.append(dict(proposal_id='parent_child_scope',method='restrict_children_to_explicit_parent_route',patches=patch,
     source_quotations=[acid[0],ester[0]],no_unreported_ester_pressure_or_nitrogen_inherited=True))
  for method,pattern in [('hydroxyl_endgroup_acetylation',ACETYL),('final_polyester_selection_requirement',MINIMUM)]:
   for q in cache['source_quotations']:
    m=pattern.search(q['text'])
    if not m:continue
    origin=pred['property_source'];occ=[o for o in q['occurrences'] if o['source_path']==origin['path']]
    if not occ:continue
    if method=='final_polyester_selection_requirement':
     ids={s['id'] for s in pg.get('states',[])}
     if not {'S3','E4','H2','HC','M1'}<=ids:continue
     targets=[dict(path='/process_graph/states/'+str(i),state_id=s['id']) for i,s in enumerate(pg['states']) if s['id'] in ['S3','E4','H2','HC','M1']]
    else:
     if not any('polyester' in op.get('applies_to',[''])[0].lower() for op in pg.get('operations',[]) if op.get('applies_to')):continue
     targets=[]
    proposals.append(dict(proposal_id=method,method=method,literal=capture(q,m),existing_final_state_targets=targets,
     analytical_branch_not_synthesis=True if method=='hydroxyl_endgroup_acetylation' else False,
     transient_2000_precursors_excluded=True if method=='final_polyester_selection_requirement' else False))
  dest=DEST/'papers'/(p['reference_no']+'.json');save(dest,dict(reference_no=p['reference_no'],candidate_input=p,property_source=pred['property_source'],
   cache_path=str(cp),cache_sha256=sha(cp),proposals=proposals,accepted_into_prediction=False,reference_answers_or_scores_read=False,new_pdf_information_extracted=0,external_api_calls=0))
  rows.append(dict(reference_no=p['reference_no'],path=str(dest),sha256=sha(dest),proposals=len(proposals)))
 save(DEST/'manifest.json',dict(papers=rows,papers_scanned=len(rows),groups=sum(p['proposals'] for p in rows),generator_code_sha256=sha(__file__),
  baseline_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),reference_answers_or_scores_read=False,new_pdf_information_extracted=0,external_api_calls=0))
 print({'scanned':len(rows),'groups':sum(p['proposals'] for p in rows),'papers_with_proposals':sum(bool(p['proposals']) for p in rows)})


if __name__=='__main__':main()
