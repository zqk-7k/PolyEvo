from copy import deepcopy
from prepare_audit import OUT,read,save,sha

TRIAL=OUT/'process_relation_trial_010'
EXTENSION='process_saved_polyimide_dsc_history_recovery'


def build(r,a):
 c=r['captures'];v=lambda k:c[k]['value_raw'];ops=[];states=[];orders=[];bindings=[]
 label=v('main_label')
 def par(role,key,unit=None):
  return dict(role=role,value_raw=v(key),unit_raw=unit,source_capture=key,source_quote_span=c[key]['original_quote_span'])
 def state(i,sample,text,**kw):states.append(dict(id=i,kind='state',sample=sample,state=text,**kw))
 def op(i,sample,name,ins,outs,pars):
  ops.append(dict(id=i,kind='operation',sample=sample,name=name,inputs=ins,outputs=outs,parameters=pars))
  bindings.append(dict(id='SCOPE_'+i,kind='binding',sample=sample,operation_id=i,input_states=ins,output_states=outs,scope='explicit named DSC thermal history only'))
 def edge(i,before,after):orders.append(dict(id=i,kind='order',before=before,after=after,relation='precedes',basis='explicit run labels and reported continuation, not array order'))
 state('BTDA_GLASS_FILM_BEFORE_DRY',label,'glass-supported film before the reported final drying',chemical_conversion_at_this_input_not_asserted=True)
 state('BTDA_RUN1',label,v('initial_state')+' film after the reported glass-supported drying',existing_DSC_sample_target=r['main_DSC_target'],phase_basis='source explicitly reports x-ray confirmation, not inference from a melting temperature')
 state('BTDA_HEATED',label,'the Run 1 film heated to the reported temperature in air',complete_melting_not_asserted=True)
 state('BTDA_QUENCHED',label,v('amorphous_qualifier')+' '+v('amorphous_form')+' after the reported DSC quench',fully_amorphous_not_asserted=True,quench_medium_and_rate_not_reported=True)
 state('BTDA_AFTER_RUN2',label,'same DSC specimen after Run 2 with '+v('second_response'),original_phase_not_assumed_unchanged_during_scan=True)
 state('BTDA_AFTER_SLOW_COOL2',label,'same specimen after slow cooling following Run 2')
 state('BTDA_AFTER_RUN3',label,'same specimen after Run 3 with '+v('third_response'))
 state('BTDA_AFTER_HOLD',label,'the Run 3 specimen after the reported annealing hold in air',phase_fraction_not_asserted=True)
 state('BTDA_AFTER_SLOW_COOL3',label,'annealed specimen after the subsequent slow cooling',phase_fraction_not_asserted=True)
 state('BTDA_AFTER_RUN4',label,'same specimen after Run 4 with '+v('fourth_response'),author_qualitative_interpretation=v('recovery_interpretation'),phase_fraction_not_asserted=True)
 op('BTDA_DRY',label,v('initial_action'),['BTDA_GLASS_FILM_BEFORE_DRY'],['BTDA_RUN1'],[par('temperature','initial_temperature','°C'),par('duration','initial_duration',v('initial_time_unit')),par('atmosphere','initial_atmosphere'),par('support','substrate')])
 op('BTDA_HEAT',label,v('heating_action'),['BTDA_RUN1'],['BTDA_HEATED'],[par('temperature','quench_temperature','°C'),par('atmosphere','quench_heating_atmosphere')])
 op('BTDA_QUENCH',label,v('quench_action'),['BTDA_HEATED'],['BTDA_QUENCHED'],[])
 op('BTDA_RUN2',label,v('second_run'),['BTDA_QUENCHED'],['BTDA_AFTER_RUN2'],[])
 op('BTDA_SLOW_COOL2',label,v('second_cooling'),['BTDA_AFTER_RUN2'],['BTDA_AFTER_SLOW_COOL2'],[])
 op('BTDA_RUN3',label,v('third_run'),['BTDA_AFTER_SLOW_COOL2'],['BTDA_AFTER_RUN3'],[])
 op('BTDA_HOLD',label,v('anneal_action'),['BTDA_AFTER_RUN3'],['BTDA_AFTER_HOLD'],[par('temperature','anneal_temperature','°C'),par('duration','anneal_duration',v('anneal_time_unit')),par('atmosphere','anneal_atmosphere')])
 op('BTDA_SLOW_COOL3',label,v('third_cooling'),['BTDA_AFTER_HOLD'],['BTDA_AFTER_SLOW_COOL3'],[])
 op('BTDA_RUN4',label,v('fourth_run'),['BTDA_AFTER_SLOW_COOL3'],['BTDA_AFTER_RUN4'],[])
 main_ids=[x['id'] for x in ops]
 for j,(before,after) in enumerate(zip(main_ids,main_ids[1:])):edge('BTDA_SEQUENCE_'+str(j),before,after)
 bindings.append(dict(id='BTDA_DSC_IDENTITY',kind='binding',sample=label,output_state='BTDA_RUN1',existing_sample_targets=[r['main_DSC_target']],relation='named DSC specimen identity only; does not transfer mechanical-specimen history'))
 for j,target in enumerate(r['control_material_targets']):
  pre='CONTROL_'+str(j);name=target['label'];initial=pre+'_FILM';held=pre+'_HELD';cooled=pre+'_COOLED';rescanned=pre+'_RESCANNED'
  state(initial,name,'cured polyimide DSC film before the reported annealing control',existing_material_identity_target=target,material_identity_not_mechanical_specimen_transfer=True)
  state(held,name,'film after the reported annealing-duration range',range_not_expanded_into_individual_experiments=True)
  state(cooled,name,'annealed film after slow cooling')
  state(rescanned,name,'DSC-rerun film; no melting transition reported again',absence_of_Tm_not_equated_to_fully_amorphous=True)
  duration=dict(role='reported duration range',value_raw=v('control_minimum')+'–'+v('control_maximum'),unit_raw=v('control_time_unit'),source_captures=['control_minimum','control_maximum','control_time_unit'],range_not_expanded_into_individual_experiments=True)
  op(pre+'_ANNEAL',name,v('control_action'),[initial],[held],[par('temperature','control_temperature','°C'),duration])
  op(pre+'_SLOW_COOL',name,v('control_cooling'),[held],[cooled],[])
  op(pre+'_RERUN',name,v('control_rerun'),[cooled],[rescanned],[])
  edge(pre+'_SEQUENCE_0',pre+'_ANNEAL',pre+'_SLOW_COOL');edge(pre+'_SEQUENCE_1',pre+'_SLOW_COOL',pre+'_RERUN')
  bindings.append(dict(id=pre+'_MATERIAL_IDENTITY',kind='binding',sample=name,output_state=rescanned,existing_sample_targets=[target],relation='named material identity only, not a physical mechanical-test batch transfer'))
 return dict(proposal_id=r['proposal_id'],operations=ops,parameters=[],states=states,orders=orders,bindings=bindings,saved_quote=r['saved_quote'],captures=c,source_approval_path=a['path'],source_approval_sha256=a['sha256'],mechanical_quenched_test_specimens_not_used=True,quench_medium_heating_rates_and_unreported_scan_endpoints_not_recovered=True,property_transition_values_not_promoted_to_process_parameters=True,new_pdf_information_extracted=0)


def main():
 pp=OUT/'process_relation_trial_009/freeze.json';parent=read(pp);approved={x['reference_no']:x for x in read(OUT/'saved_polyimide_dsc_history_recovery/source_reviews/manifest.json')['papers']};rows=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no'] in approved:
   a=approved[p['reference_no']];assert sha(a['path'])==a['sha256'];ap=read(a['path']);assert sha(ap['proposal_path'])==ap['proposal_sha256'];packet=read(ap['proposal_path']);old=read(p['candidate_path']);new=deepcopy(old);new[EXTENSION]=[build(packet['proposals'][0],a)];dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new);row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  rows.append(row)
 save(TRIAL/'freeze.json',dict(version='process_relation_trial_010',parent_trial='process_relation_trial_009',parent_trial_freeze_sha256=sha(pp),baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),proposal_generation_code_sha256=sha(OUT/'propose_saved_polyimide_dsc_history.py'),papers=rows,papers_total=101,cumulative_changed_papers=sum(bool(p.get('changed_from_parent')) for p in rows),changed_papers_this_round=1,property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,existing_candidate_process_fields_revised=0,reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,stable_workflow_release=False,external_api_calls=0));print({'papers':101,'changed_this_round':1,'cumulative_changed_papers':sum(bool(p.get('changed_from_parent')) for p in rows)})

if __name__=='__main__':main()
