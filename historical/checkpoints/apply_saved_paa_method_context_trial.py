"""Apply only approved literal condition additions, retaining all prior fields."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha,canonical
from inspect_fixed_pair import resolve

TRIAL=OUT/'process_relation_trial_003'


def main():
 parent_path=OUT/'process_relation_trial_002/freeze.json';parent=read(parent_path)
 approvals=read(OUT/'saved_paa_method_context/source_reviews/manifest.json');byref={x['reference_no']:x for x in approvals['papers']};papers=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no'] in byref:
   a=byref[p['reference_no']];assert sha(a['path'])==a['sha256'];approval=read(a['path']);assert approval['trial_only']
   assert sha(approval['proposal_path'])==approval['proposal_sha256'];d=read(approval['proposal_path'])
   assert d['candidate_input']['candidate_sha256']==p['candidate_sha256'];old=read(p['candidate_path']);new=deepcopy(old);groups=[]
   for decision in approval['groups']:
    assert decision['decision']=='supported_for_separate_process_side_trial';r=next(x for x in d['proposals'] if x['proposal_id']==decision['proposal_id'])
    for role in ['polymerization','casting']:assert canonical(resolve(old,r[f'existing_{role}_path']))==r[f'existing_{role}_sha256']
    for fragment in r['captured_fragments'].values():
     for value in fragment['captures'].values():
      start,end=value['original_quote_span'];assert fragment['existing_quote']['text'][start:end]==value['value_raw']
    completion=[]
    for method,key,role in [('polymerization','ratio','diamine:dianhydride molar ratio'),('casting','substrate','casting substrate')]:
     completion.append(dict(id='PAA_RATIO' if method=='polymerization' else 'PAA_GLASS',kind='parameter',
      role=role,value_raw=r['captured_fragments'][method]['captures'][key]['value_raw'],
      existing_operation_path=r[f'existing_{method}_path'],
      applies_to_actual_existing_outputs=True,unchanged_input_output_sets=True,
      source_fragment=method,source_capture=key))
    groups.append(dict(proposal_id=r['proposal_id'],condition_completions=completion,
     source_quotation_fragments=r['captured_fragments'],source_approval_path=a['path'],source_approval_sha256=a['sha256'],
     existing_quote_values_only=True,new_pdf_information_extracted=0,no_new_operations_or_samples=True))
   new['process_saved_PAA_context_recovery']=groups
   assert {k:v for k,v in new.items() if k!='process_saved_PAA_context_recovery'}==old
   dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new)
   row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,
    immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  papers.append(row)
 save(TRIAL/'freeze.json',dict(version='process_relation_trial_003',parent_trial='process_relation_trial_002',
  parent_trial_freeze_sha256=sha(parent_path),baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),
  prediction_application_code_sha256=sha(__file__),proposal_generation_code_sha256=read(OUT/'saved_paa_method_context/manifest.json')['generator_code_sha256'],
  papers=papers,papers_total=len(papers),cumulative_changed_papers=sum(p.get('changed_from_parent',False) for p in papers),
  changed_papers_this_round=sum(p['changed_from_immediate_parent'] for p in papers),
  old_properties_and_bindings_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,
  all101_scientific_targets_proven=False,stable_workflow_release=False,external_api_calls=0))
 print({'papers':len(papers),'changed_this_round':sum(p['changed_from_immediate_parent'] for p in papers),'cumulative_changed':sum(p.get('changed_from_parent',False) for p in papers)})


if __name__=='__main__':main()
