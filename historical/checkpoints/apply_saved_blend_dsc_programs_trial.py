from copy import deepcopy
from prepare_audit import OUT,read,save,sha

TRIAL=OUT/'process_relation_trial_015'
EXTENSION='process_saved_blend_dsc_programs_recovery'


def build(r,approval):
 f=r['fragments'];v=lambda g,k:f[g]['captures'][k]['value_raw'];materials=[];states=[];operations=[];parameters=[];bindings=[];measurements=[];orders=[]
 labels=list(r['existing_sample_targets']);has_sbh={label:float(label.split('/')[1])>0 for label in labels}
 def node(label,branch,stage,**extra):
  ident=f'{branch}_{stage}_{label.replace("/","_")}'
  state=dict(id=ident,kind='state',sample=label,branch=branch,stage=stage,independent_method_application=True,physical_batch_identity_unknown=True,**extra)
  states.append(state);return ident
 def par(role,g,key,unit=None):return dict(role=role,value_raw=v(g,key),unit_raw=unit,source_fragment=g,source_capture=key)
 def op(ident,name,inputs,outputs,params):
  operations.append(dict(id=ident,kind='operation',name=name,scope='shared_method_applied_independently',sample_scope=labels,inputs=inputs,outputs=outputs,parameters=params,not_a_pooled_batch=True))
 def bind(ident,operation,label,inputs,outputs,**extra):
  bindings.append(dict(id=ident,kind='binding',sample=label,operation_id=operation,input_nodes=inputs,output_states=outputs,existing_material_identity_target=r['existing_sample_targets'][label],physical_batch_identity_unknown=True,relation='independent application of the saved method to a named reported material',**extra))
 def sbh(label,g):
  return dict(component_state_material='SBH',component_state=v(g,'phase'),component_state_source_fragment=g) if has_sbh[label] else dict(SBH_absent=True)
 for label in labels:materials.append(dict(id='MAT_'+label.replace('/','_'),kind='material_identity_annotation',sample=label,existing_material_identity_target=r['existing_sample_targets'][label],phase_not_inferred=True))
 for branch in ['NI','ISO']:
  g='noniso' if branch=='NI' else 'iso';hot={};held={}
  for label in labels:
   hot[label]=node(label,branch,'HOT',state='heated calorimetry specimen',temperature=par('temperature',g,'temperature','°C'))
   held[label]=node(label,branch,'HELD',state=v('noniso','erasure'),temperature=par('temperature',g,'temperature','°C'),duration=par('duration',g,'duration','min'),**sbh(label,'noniso_phase' if branch=='NI' else 'iso_results'))
  params=[par('target temperature',g,'temperature','°C'),par('apparatus','noniso','equipment'),par('atmosphere','noniso','atmosphere')]
  if branch=='ISO':params.append(par('heating rate','iso','heating_rate','°C/min'))
  op('HEAT_'+branch,v('noniso','heating'),[x['id'] for x in materials],list(hot.values()),params)
  op('HOLD_'+branch,v('noniso','holding'),list(hot.values()),list(held.values()),[par('temperature',g,'temperature','°C'),par('duration',g,'duration','min'),par('purpose','noniso','erasure')])
  for label in labels:
   bind('HEAT_'+branch+'_'+label,'HEAT_'+branch,label,['MAT_'+label.replace('/','_')],[hot[label]])
   bind('HOLD_'+branch+'_'+label,'HOLD_'+branch,label,[hot[label]],[held[label]])
  orders.append(dict(id='HEAT_HOLD_'+branch,kind='order',before='HEAT_'+branch,after='HOLD_'+branch,scope=labels,relation='precedes_within_each_independent_application'))
  if branch=='NI':
   outputs=[]
   for k in ['rate1','rate2','rate3','rate4']:
    for label in labels:
     ident=node(label,branch,'COOL_'+v('noniso',k),state='LLDPE crystallization specimen after the reported non-isothermal cooling; endpoint temperature not recovered',cooling_rate=par('cooling rate','noniso',k,'°C/min'),**sbh(label,'noniso_phase'));outputs.append(ident)
     bind('NI_'+label+'_'+v('noniso',k),'COOL_NI',label,[held[label]],[ident],selected_cooling_rate=par('cooling rate','noniso',k,'°C/min'))
   op('COOL_NI',v('noniso','cooling'),list(held.values()),outputs,[dict(role='alternative cooling rates',values_raw=[v('noniso',k) for k in ['rate1','rate2','rate3','rate4']],unit_raw='°C/min',source_fragment='noniso',source_captures=['rate1','rate2','rate3','rate4']),par('atmosphere','noniso','atmosphere')])
   orders.append(dict(id='HOLD_COOL_NI',kind='order',before='HOLD_NI',after='COOL_NI',scope=labels,relation='precedes_within_each_independent_application'))
  else:
   quick=[];crystallized=[]
   for i,row in enumerate(r['actual_isothermal_pairs']):
    label=row['sample_label'];pid=f'TC_{i:02}';temperature=dict(id=pid,kind='parameter',role='actual specimen crystallization temperature',value_raw=row['temperature_raw'],unit_raw=row['unit_raw'],sample=label,applies_to_operation_ids=['QUICK_COOL_ISO','CRYST_ISO'],source_existing_point=row['existing_point_path'],source_table_header_fragment='table2_header',unit_role_basis=row['unit_role_basis']);parameters.append(temperature)
    suffix=row['temperature_raw'];a=node(label,branch,'COOL_'+suffix,state='rapidly cooled specimen at this actual reported Tc',parameter_ids=[pid],cooling_rate=par('cooling rate','iso','cooling_rate','°C/min'),**sbh(label,'iso_results'));quick.append(a)
    b=node(label,branch,'CRYST_'+suffix,state='isothermally crystallized LLDPE specimen before direct melting-temperature measurement',parameter_ids=[pid],endpoint=par('endpoint','iso','endpoint'),fixed_hold_duration_not_reported=True,**sbh(label,'iso_results'));crystallized.append(b)
    bind('QUICK_'+str(i),'QUICK_COOL_ISO',label,[held[label]],[a],parameter_ids=[pid])
    mid='TM_'+str(i);measurements.append(dict(id=mid,kind='measurement_context_annotation',sample=label,prepared_state=b,parameter_ids=[pid],measurement=v('melting_consumer','measurement'),input_description=v('melting_consumer','input'),measurement_follows_directly_from_Tc=True,scan_rate=par('measurement heating rate','melting_consumer','measurement_rate','°C/min'),pure_measurement_not_a_preparation_operation=True))
    bind('CRYST_'+str(i),'CRYST_ISO',label,[a],[b],parameter_ids=[pid],measurement_annotation=mid)
   op('QUICK_COOL_ISO',v('iso','cooling'),list(held.values()),quick,[par('cooling rate','iso','cooling_rate','°C/min'),dict(role='experimental protocol nominal Tc range',value_min_raw=v('iso','lower'),value_max_raw=v('iso','upper'),unit_raw='°C',source_fragment='iso',source_captures=['lower','upper']),dict(role='results-section observed Tc range',value_min_raw=v('iso_results','lower'),value_max_raw=v('iso_results','upper'),unit_raw='°C',source_fragment='iso_results',source_captures=['lower','upper'],not_silently_substituted_for_experimental_range=True)])
   op('CRYST_ISO',v('iso','operation'),quick,crystallized,[par('completion endpoint','iso','endpoint')])
   for ident,left,right in [('HOLD_QUICK_ISO','HOLD_ISO','QUICK_COOL_ISO'),('QUICK_CRYST_ISO','QUICK_COOL_ISO','CRYST_ISO')]:orders.append(dict(id=ident,kind='order',before=left,after=right,scope='each actual sample/Tc pair, separately',relation='precedes_within_each_independent_application'))
 return dict(proposal_id=r['proposal_id'],materials=materials,states=states,operations=operations,parameters=parameters,orders=orders,bindings=bindings,measurement_annotations=measurements,saved_fragments=f,actual_isothermal_pairs=r['actual_isothermal_pairs'],corroborating_explicit_Tc_points=r['corroborating_explicit_Tc_points'],source_approval_path=approval['path'],source_approval_sha256=approval['sha256'],alternative_DSC_histories_not_serialized=True,no_thermal_state_assigned_to_unreported_combination=True,no_SBH_state_for_zero_SBH=True,original_property_values_and_units_not_changed=True,half_crystallization_times_not_hold_durations=True,new_pdf_information_extracted=0)


def main():
 parentpath=OUT/'process_relation_trial_014/freeze.json';parent=read(parentpath);approved={x['reference_no']:x for x in read(OUT/'saved_blend_dsc_programs_recovery/source_reviews/manifest.json')['papers']};rows=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no'] in approved:
   a=approved[p['reference_no']];assert sha(a['path'])==a['sha256'];review=read(a['path']);assert sha(review['proposal_path'])==review['proposal_sha256'];packet=read(review['proposal_path']);old=read(p['candidate_path']);new=deepcopy(old);new[EXTENSION]=[build(packet['proposals'][0],a)];dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new);row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  rows.append(row)
 save(TRIAL/'freeze.json',dict(version=TRIAL.name,parent_trial='process_relation_trial_014',parent_trial_freeze_sha256=sha(parentpath),baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),proposal_generation_code_sha256=sha(OUT/'propose_saved_blend_dsc_programs.py'),papers=rows,papers_total=101,changed_papers_this_round=1,cumulative_changed_papers=sum(bool(p.get('changed_from_parent')) for p in rows),property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,stable_workflow_release=False,external_api_calls=0));print({'papers':len(rows),'changed_this_round':1,'cumulative_changed_papers':sum(bool(p.get('changed_from_parent')) for p in rows)})

if __name__=='__main__':main()
