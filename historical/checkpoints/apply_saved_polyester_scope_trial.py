"""Make a new process-only candidate; frozen originals and property bindings stay intact."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha,canonical
from inspect_fixed_pair import resolve

TRIAL=OUT/'process_relation_trial_006'
EXTENSION='process_saved_polyester_qualification_recovery'


def build_groups(proposals,a):
 groups=[]
 for r in proposals:
  if r['method']=='restrict_children_to_explicit_parent_route':continue
  f=r['literal']['captures'];v=lambda k:f[k]['value_raw']
  if r['method']=='hydroxyl_endgroup_acetylation':
   operations=[dict(id='A_ACETYLATE',kind='operation',name='Acetylate polyester hydroxyl end groups for the reported analytical method',
    output_state='A_DERIVATIZED',parameters=[dict(role='analytical derivatization reagent',value_raw=v('reagent'),source_capture='reagent')])]
   states=[dict(id='A_DERIVATIZED',kind='state',state='polyester analytical specimen subjected to hydroxyl-end-group acetylation',operation='A_ACETYLATE',quantitative_conversion_not_assigned=True)]
   parameters=[];bindings=[dict(id='A_METHOD_SCOPE',kind='binding',operation_id='A_ACETYLATE',output_state='A_DERIVATIZED',scope='polyester hydroxyl-end-group analytical derivatization, not polymer synthesis or carboxyl titration',individual_batch_assignment_not_reported=True)]
  else:
   assert r['method']=='final_polyester_selection_requirement';operations=[];states=[]
   parameters=[dict(id='MW_SELECTION',kind='parameter',role='reported minimum molecular weight of final polyester materials used for glass-transition comparison',
    value_raw=v('minimum'),relation=v('relation'),source_capture='minimum',relation_source_capture='relation',
    is_selection_requirement_not_new_measurement_or_reaction_stopping_criterion=True,transient_low_MW_chain_extension_precursors_excluded=True)]
   bindings=[dict(id='MW_SCOPE_'+str(i+1),kind='binding',qualification_id='MW_SELECTION',existing_state_path=t['path'],existing_state_id=t['state_id'],
    relation='reported_selection_requirement_for_final_polyester_material_or_constituents_used_in_assay',does_not_invent_individual_molecular_weight_value=True) for i,t in enumerate(r['existing_final_state_targets'])]
  groups.append(dict(proposal_id=r['proposal_id'],method=r['method'],operations=operations,parameters=parameters,states=states,orders=[],bindings=bindings,
   literal=r['literal'],source_approval_path=a['path'],source_approval_sha256=a['sha256'],unknown_conditions_not_filled=True,new_pdf_information_extracted=0))
 return groups


def main():
 pp=OUT/'process_relation_trial_005/freeze.json';parent=read(pp);approved={a['reference_no']:a for a in read(OUT/'saved_polyester_scope_repair/source_reviews/manifest.json')['papers']};rows=[];changes=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no'] in approved:
   a=approved[p['reference_no']];assert sha(a['path'])==a['sha256'];approval=read(a['path']);assert sha(approval['proposal_path'])==approval['proposal_sha256'];packet=read(approval['proposal_path'])
   old=read(p['candidate_path']);new=deepcopy(old);approved_ids={x['proposal_id'] for x in approval['groups'] if x['decision']=='supported_for_separate_process_side_trial'}
   accepted=[r for r in packet['proposals'] if r['proposal_id'] in approved_ids]
   for r in accepted:
    for patch in r.get('patches',[]):
     assert resolve(new,patch['path'])==patch['before'];parentpath,key=patch['path'].rsplit('/',1);resolve(new,parentpath)[key]=deepcopy(patch['after'])
     changes.append(dict(reference_no=p['reference_no'],path=patch['path'],before=patch['before'],after=patch['after'],before_sha256=canonical(patch['before']),after_sha256=canonical(patch['after']),
      gain_category='existing_parameter_scope_repair_not_new_extraction',source_approval_path=a['path'],source_approval_sha256=a['sha256']))
   new[EXTENSION]=build_groups(accepted,a);assert len(new[EXTENSION])==2 and new['property_source']==old['property_source']
   dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new);row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,
    immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  rows.append(row)
 save(TRIAL/'process_scope_changes.json',dict(changes=changes,external_api_calls=0));assert len(changes)==9
 save(TRIAL/'freeze.json',dict(version='process_relation_trial_006',parent_trial='process_relation_trial_005',parent_trial_freeze_sha256=sha(pp),
  baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),
  proposal_generation_code_sha256=sha(OUT/'propose_saved_polyester_scope_repair.py'),papers=rows,papers_total=101,
  cumulative_changed_papers=sum(bool(p.get('changed_from_parent')) for p in rows),changed_papers_this_round=1,
  process_scope_change_ledger_path=str(TRIAL/'process_scope_changes.json'),process_scope_change_ledger_sha256=sha(TRIAL/'process_scope_changes.json'),
  frozen_original_outputs_modified=False,property_content_or_bindings_modified=False,existing_candidate_process_fields_revised=9,
  reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,all101_scientific_targets_proven=False,stable_workflow_release=False,external_api_calls=0))
 print({'papers':101,'changed_this_round':1,'cumulative_changed_papers':sum(bool(p.get('changed_from_parent')) for p in rows),'process_scope_fields_repaired':9})


if __name__=='__main__':main()
