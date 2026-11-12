"""Apply approved saved-source proposals; do not read reference or scores."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha

TRIAL=OUT/'process_relation_trial_005'
EXTENSION='process_saved_fraction_dsc_recovery'


def build_group(r,a):
 f=r['captures']
 def par(role,key):return dict(role=role,value_raw=f[key]['value_raw'],source_capture=key)
 if r['method']=='soluble_fraction_workup':
  ops=[dict(id='F_EXTRACT',kind='operation',name='Extract the soluble polymer fraction',output_state='F_EXTRACTED',parameters=[par('extraction solvent','solvent')]),
   dict(id='F_REPRECIP',kind='operation',name='Reprecipitate the extracted soluble fraction',input_state='F_EXTRACTED',output_state='F_REPRECIPITATED',parameters=[par('precipitation medium','medium')])]
  states=[dict(id='F_EXTRACTED',kind='state',state='chloroform-extracted soluble polymer fraction',operation='F_EXTRACT'),
   dict(id='F_REPRECIPITATED',kind='state',state='soluble fraction reprecipitated from methanol',operation='F_REPRECIP',reported_uses=f['uses']['value_raw'],uses_source_capture='uses')]
  orders=[dict(id='F_ORDER',kind='order',before='F_EXTRACT',after='F_REPRECIP',relation='explicit_then_same_soluble_fraction')]
  bindings=[dict(id='F_SCOPE1',kind='binding',operation_id='F_EXTRACT',output_state='F_EXTRACTED',identity_names=r['source_local_identity_names']),
   dict(id='F_SCOPE2',kind='binding',operation_id='F_REPRECIP',input_state='F_EXTRACTED',output_state='F_REPRECIPITATED',identity_names=r['source_local_identity_names'],reported_uses=f['uses']['value_raw'])]
 else:
  assert r['method']=='successive_dsc_states'
  ops=[dict(id='D_QUENCH',kind='operation',name=f['quench']['value_raw'],input_state='D_INITIAL',output_state='D_QUENCHED',parameters=[]),
   dict(id='D_SLOWCOOL',kind='operation',name='Cool the same DSC sample in the subsequently reported thermal history',input_state='D_QUENCHED',output_state='D_SLOWCOOLED',
    intervening_thermal_history='DSC observation after quenching; exact intervening heating conditions not reconstructed',parameters=[par('subsequent cooling condition','cool')])]
  states=[dict(id='D_INITIAL',kind='state',state=f['initial']['value_raw'],source_capture='initial',curve='DSC curve 1',existing_sample_anchor=r['existing_identity_anchors'][1]),
   dict(id='D_QUENCHED',kind='state',state=f['amorphous']['value_raw'],state_source_capture='amorphous',curve='DSC curve 2',operation='D_QUENCH',subsequent_dsc_observation=f['partial']['value_raw'],observation_source_capture='partial',existing_sample_anchor=r['existing_identity_anchors'][0]),
   dict(id='D_SLOWCOOLED',kind='state',state=f['after']['value_raw'],state_source_capture='after',operation='D_SLOWCOOL',subsequent_dsc_observation=f['no_melt']['value_raw'],observation_source_capture='no_melt')]
  orders=[dict(id='D_ORDER',kind='order',before='D_QUENCH',after='D_SLOWCOOL',relation='subsequent_history_with_intervening_DSC_not_immediate_step')]
  bindings=[dict(id='D_SCOPE1',kind='binding',operation_id='D_QUENCH',input_state='D_INITIAL',output_state='D_QUENCHED',identity_names=r['source_local_identity_names']),
   dict(id='D_SCOPE2',kind='binding',operation_id='D_SLOWCOOL',input_state='D_QUENCHED',output_state='D_SLOWCOOLED',identity_names=r['source_local_identity_names'],intervening_DSC_observation_preserved=True)]
 return dict(proposal_id=r['proposal_id'],method=r['method'],operations=ops,states=states,orders=orders,bindings=bindings,
  literal_source_captures=f,existing_quote=r['existing_quote'],existing_identity_anchors=r['existing_identity_anchors'],original_common_source_block_ids=r['original_common_source_block_ids'],
  source_approval_path=a['path'],source_approval_sha256=a['sha256'],physical_batch_identity_not_inferred=True,unknown_conditions_not_filled=True,new_pdf_information_extracted=0)


def main():
 pp=OUT/'process_relation_trial_004/freeze.json';parent=read(pp);approvals={x['reference_no']:x for x in read(OUT/'saved_fraction_and_dsc_context/source_reviews/manifest.json')['papers']};rows=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no'] in approvals:
   a=approvals[p['reference_no']];assert sha(a['path'])==a['sha256'];approval=read(a['path']);assert sha(approval['proposal_path'])==approval['proposal_sha256'];proposal=read(approval['proposal_path'])
   old=read(p['candidate_path']);assert old['property_source']==proposal['property_source'];new=deepcopy(old)
   accepted={x['proposal_id'] for x in approval['groups'] if x['decision']=='supported_for_separate_process_side_trial'}
   new[EXTENSION]=[build_group(r,a) for r in proposal['proposals'] if r['proposal_id'] in accepted];assert len(new[EXTENSION])==1
   assert {k:v for k,v in new.items() if k!=EXTENSION}==old
   dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new);row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,
    immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  rows.append(row)
 save(TRIAL/'freeze.json',dict(version='process_relation_trial_005',parent_trial='process_relation_trial_004',parent_trial_freeze_sha256=sha(pp),
  baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),
  proposal_generation_code_sha256=sha(OUT/'propose_saved_fraction_and_dsc_context.py'),papers=rows,papers_total=101,
  cumulative_changed_papers=sum(bool(p.get('changed_from_parent')) for p in rows),changed_papers_this_round=2,
  old_properties_and_bindings_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,
  all101_scientific_targets_proven=False,stable_workflow_release=False,external_api_calls=0))
 print({'papers':101,'changed_this_round':2,'cumulative_changed_papers':sum(bool(p.get('changed_from_parent')) for p in rows)})


if __name__=='__main__':main()
