"""Incremental proposal application. No reference, scoring or PDF/source inputs."""
from prepare_audit import OUT,read,save,sha,canonical
from inspect_fixed_pair import resolve
from copy import deepcopy

TRIAL=OUT/'process_relation_trial_002'


def main():
 parent_path=OUT/'process_relation_trial_001/freeze.json';parent=read(parent_path)
 approvals=read(OUT/'saved_q_swelling_protocol/source_reviews/manifest.json');byref={x['reference_no']:x for x in approvals['papers']};papers=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no'] in byref:
   a=byref[p['reference_no']];assert sha(a['path'])==a['sha256'];approval=read(a['path']);assert approval['trial_only']
   assert sha(approval['proposal_path'])==approval['proposal_sha256'];d=read(approval['proposal_path']);assert d['candidate_input']['candidate_sha256']==p['candidate_sha256']
   old=read(p['candidate_path']);new=deepcopy(old);origin=old['property_source'];assert sha(origin['path'])==origin['sha256'];prop=read(origin['path']);groups=[]
   for decision in approval['groups']:
    assert decision['decision']=='supported_for_separate_process_side_trial'
    r=next(r for r in d['proposals'] if r['proposal_id']==decision['proposal_id']);assert canonical(resolve(old,r['specimen_path']))==r['specimen_sha256']
    assert canonical(resolve(old,r['specimen_producer_path']))==r['specimen_producer_sha256'];assert canonical(resolve(prop,r['characterization_path']))==r['characterization_sha256']
    for name,f in r['captured_fragments'].items():
     for key,v in f['captures'].items():
      start,end=v['original_quote_span'];assert f['existing_quote']['text'][start:end]==v['value_raw']
    def val(fragment,key):return r['captured_fragments'][fragment]['captures'][key]['value_raw']
    def param(role,fragment,key):return dict(role=role,value_raw=val(fragment,key),fragment=fragment,capture=key)
    stock=[param('stock crosslinker loading','selection','loading'),param('crosslinker','selection','agent'),param('prior vulcanization time','selection','cure_time'),param('prior vulcanization temperature','selection','cure_temperature')]
    scope=dict(id='Q_SCOPE',kind='binding',existing_specimen_path=r['specimen_path'],existing_producer_path=r['specimen_producer_path'],
     relation='reported_assay_selects_this_condition_from_parent_stock_series',assay='swelling coefficient [Q]',
     selected_input_conditions=stock,selected_specimen_not_entire_parent_range=True,entity_id=r['entity_id'])
    charlink=dict(id='Q_CHARACTERIZATION',kind='binding',characterization_source_path=r['characterization_path'],
     property_source_sha256=origin['sha256'],existing_specimen_path=r['specimen_path'],
     relation='existing_Q_characterization_applies_to_selected_processed_specimen',old_property_binding_unchanged=True)
    operations=[
     dict(id='Q_SWELL',name='Swell selected specimens in independent solvents',kind='operation',
      input_existing_specimen_path=r['specimen_path'],output_state='Q_SWOLLEN',scope='independent_solvent_applications',
      parameters=[param('solvent scope','swelling','solvent_scope'),param('antioxidant fraction, basis unspecified','swelling','antioxidant_fraction'),
       param('antioxidant identity','swelling','antioxidant'),param('swelling temperature','swelling','temperature'),
       param('period sufficient for equilibrium','equilibrium','duration')]),
     dict(id='Q_AIR_DRY',name='Air-oven dry post-swelling specimens',kind='operation',input_state='Q_SWOLLEN',output_state='Q_AIR_DRIED',
      parameters=[param('equipment','drying','equipment'),param('duration','drying','duration'),param('temperature','drying','temperature')]),
     dict(id='Q_VAC_DRY',name='Finally dry post-swelling specimens in vacuum',kind='operation',input_state='Q_AIR_DRIED',output_state='Q_FINAL_DRY',
      parameters=[param('original vacuum notation','drying','vacuum')])]
    states=[dict(id='Q_SWOLLEN',kind='state',entity_id=r['entity_id'],existing_input_specimen_path=r['specimen_path'],
      state='equilibrium-swollen selected Q specimens; independent solvent instances',
      observation=param('reported equilibrium observation','equilibrium','observation'),
      period=param('period sufficient for equilibrium','equilibrium','duration'),stock_definition='Q_SCOPE'),
     dict(id='Q_AIR_DRIED',kind='state',entity_id=r['entity_id'],state='post-swelling air-oven-dried Q specimens',operation='Q_AIR_DRY',stock_definition='Q_SCOPE'),
     dict(id='Q_FINAL_DRY',kind='state',entity_id=r['entity_id'],state='finally vacuum-dried Q specimens for dry-mass determination',operation='Q_VAC_DRY',stock_definition='Q_SCOPE')]
    orders=[dict(id='Q_ORDER_PUNCH_SWELL',kind='order',before_existing_operation_path=r['specimen_producer_path'],after='Q_SWELL',relation='precedes'),
     dict(id='Q_ORDER_SWELL_AIR',kind='order',before='Q_SWELL',after='Q_AIR_DRY',relation='precedes_not_necessarily_immediately',
      source_same_block_anaphora_scope_approved=True),
     dict(id='Q_ORDER_AIR_VAC',kind='order',before='Q_AIR_DRY',after='Q_VAC_DRY',relation='explicit_then')]
    groups.append(dict(proposal_id=r['proposal_id'],specimen_scope=scope,characterization_link=charlink,operations=operations,states=states,orders=orders,
     source_quotation_fragments=r['captured_fragments'],source_approval_path=a['path'],source_approval_sha256=a['sha256'],
     original_common_source_block_id=r['original_common_source_block_id'],
     existing_quote_values_only=True,new_pdf_information_extracted=0,observation_time_points_not_recovered=[],
     surface_drying_not_recovered=True,no_Hummel_stock_scope_transfer=True))
   new['process_saved_Q_protocol_recovery']=groups;assert {k:v for k,v in new.items() if k!='process_saved_Q_protocol_recovery'}==old
   dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new)
   row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,
    immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  papers.append(row)
 save(TRIAL/'freeze.json',dict(version='process_relation_trial_002',parent_trial='process_relation_trial_001',
  parent_trial_freeze_sha256=sha(parent_path),baseline_candidate='candidate_v10',
  baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),
  proposal_generation_code_sha256=read(OUT/'saved_q_swelling_protocol/manifest.json')['generator_code_sha256'],
  papers=papers,papers_total=len(papers),cumulative_changed_papers=sum(p.get('changed_from_parent',False) for p in papers),
  changed_papers_this_round=sum(p['changed_from_immediate_parent'] for p in papers),
  old_properties_and_bindings_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,
  new_pdf_information_extracted=0,all101_scientific_targets_proven=False,stable_workflow_release=False,external_api_calls=0))
 print({'papers':len(papers),'cumulative_changed_papers':sum(p.get('changed_from_parent',False) for p in papers),
  'changed_this_round':sum(p['changed_from_immediate_parent'] for p in papers),'properties_changed':False,'release':False})


if __name__=='__main__':main()
