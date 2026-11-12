"""Apply old shared methods to actual identified assay specimens, not all pairs."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha

TRIAL=OUT/'process_relation_trial_020'
EXTENSION='process_saved_membrane_specimen_links_recovery'


def build(p,approval):
 f=deepcopy(p['fragments']);methods=p['existing_method_prototypes'];states=[];bindings=[];ops=[];orders=[];index={};pairs_index=[]
 def state(ident,identity,stage,text,fragment,**kw):
  index[ident]=len(states);states.append(dict(id=ident,kind='state',identity=identity,stage=stage,state=text,source_fragment=fragment,**kw));return ident
 def binding(ident,fragment,**kw):bindings.append(dict(id='B_'+ident,kind='binding',source_fragment=fragment,**kw))
 def par(role,value,unit=None):
  x=dict(role=role,value_raw=value)
  if unit:x['unit_normalized']=unit
  return x
 caps=f['uptake']['captures'];ops.append(dict(id='UPTAKE_WEIGH',kind='operation',name='weigh dry uptake film before immersion',scope=[a['identity'] for a in p['existing_individual_polymer_inputs']],parameters=[par('film dimension',caps['length']['value_raw'],'mm'),par('other film dimension',caps['width']['value_raw'],'mm')],source_fragment='uptake',numerical_mass_and_balance_unspecified=True,no_cutting_step_inferred=True))
 for a in p['existing_individual_polymer_inputs']:
  name=a['identity'];stem=name.replace('-','_');previous=None
  for j,prototype in enumerate(p['existing_casting_state_prototypes']):
   sid=state(stem+'_CAST_'+str(j),name,'membrane preparation stage '+str(j),prototype['state'],'cast_head' if j<3 else 'cast_tail',existing_state_prototype=prototype,original_sample_identity_pointer=a['pointer'],ionic_form='sodium salt' if j<=5 else 'acid',shared_preparation_application=True,does_not_assert_common_batch=True)
   binding(sid,'cast_head' if j<3 else 'cast_tail',input_state_id=previous,output_state_id=sid,input_sample_identity_pointer=a['pointer'],operation_pointer=None if j==0 else methods['casting'][j-1]['pointer'],relation='material_identity' if j==0 else 'shared_preparation_applies_to_named_membrane',distinct_polymers_not_pooled=True);previous=sid
  acid=previous
  dry=state(stem+'_UPTAKE_DRY',name,'uptake dry reference before weighing','acid membrane after 120°C/24h vacuum drying','uptake',ionic_form='acid',operation_pointer=methods['uptake_drying'][0]['pointer'],assay='water uptake',method_application_only_not_same_physical_cast_batch=True)
  binding(dry,'uptake',input_state_id=acid,output_state_id=dry,operation_pointer=methods['uptake_drying'][0]['pointer'],relation='assay_method_applies_to_named_acid_membrane',same_physical_batch_not_asserted=True)
  weighed=state(stem+'_UPTAKE_WEIGHED',name,'before water immersion','weighed dry acid membrane; 5 mm by 50 mm film','uptake',ionic_form='acid',operation_id='UPTAKE_WEIGH',assay='water uptake',numerical_mass_unknown=True)
  binding(weighed,'uptake',input_state_id=dry,output_state_id=weighed,operation_id='UPTAKE_WEIGH',relation='dry_reference_then_weighing')
  cond=state(stem+'_CONDUCTIVITY_HYDRATED',name,'before transverse conductivity assay','acid membrane hydrated in deionized water for 24 h at room temperature; disc diameter 13 mm','conductivity',ionic_form='acid',assay='transverse proton conductivity',operation_pointer=methods['conductivity_hydration'][0]['pointer'],diameter_raw=f['conductivity']['captures']['diameter']['value_raw'],diameter_unit='mm',uptake_drying_and_geometry_not_transferred=True)
  binding(cond,'conductivity',input_sample_identity_pointer=a['pointer'],output_state_id=cond,operation_pointer=methods['conductivity_hydration'][0]['pointer'],relation='independent_conductivity_specimen_method_application',not_transfer_from_uptake_specimen=True)
 for pair in p['actual_uptake_pairs']:
  name=pair['identity'];stem=name.replace('-','_');temp=pair['temperature_raw'];sid=stem+'_UPTAKE_'+temp;opid='IMMERSE_'+sid
  ops.append(dict(id=opid,kind='operation',name='immerse weighed dry acid uptake film',scope=name,parameters=[par('medium','deionized water'),par('immersion duration','24','h'),par('immersion temperature',temp,pair['temperature_unit_normalized'])],input_state_id=stem+'_UPTAKE_WEIGHED',output_state_id=sid,source_fragment='uptake',actual_reported_property_point_anchors=deepcopy(pair['actual_reported_point_anchors']),temperature_alternatives_not_chronological_steps=True))
  state(sid,name,'after water uptake exposure','acid membrane after 24 h deionized-water immersion at '+temp+'°C','uptake',ionic_form='acid',assay='water uptake',operation_id=opid,actual_reported_point_anchors=deepcopy(pair['actual_reported_point_anchors']),separate_condition_specimen=True)
  binding(sid,'uptake',input_state_id=stem+'_UPTAKE_WEIGHED',output_state_id=sid,operation_id=opid,relation='actual_reported_sample_temperature_assay_pair',sample_and_temperature_from_existing_numeric_point=True,physical_reuse_across_temperatures_not_asserted=True)
  orders.append(dict(id='WEIGH_BEFORE_'+sid,kind='order',before_operation_id='UPTAKE_WEIGH',after_operation_id=opid,scope=name,source_fragment='uptake',relation='weigh_dry_reference_before_this_immersion',not_sequence_between_temperatures=True));pairs_index.append(dict(identity=name,temperature_raw=temp,state_index=index[sid],operation_index=len(ops)-1))
 fail=f['boil_failure']['captures'];name=fail['identity']['value_raw'];stem=name.replace('-','_');sid=stem+'_BOILING_FAILURE';opid='IMMERSE_BOILING_FAILURE'
 ops.append(dict(id=opid,kind='operation',name=fail['exposure']['value_raw'],scope=name,input_state_id=stem+'_UPTAKE_WEIGHED',output_state_id=sid,temperature_description='boiling water',parameters=[par('medium','water'),par('exposure duration',fail['duration']['value_raw'],'h')],source_fragment='boil_failure',numerical_temperature_not_inferred=True,missing_numeric_uptake_not_filled=True))
 state(sid,name,'after reported boiling-water exposure',fail['outcome']['value_raw'],'boil_failure',ionic_form='acid',operation_id=opid,assay='qualitative water-exposure outcome',numeric_water_uptake_not_reported=True)
 binding(sid,'boil_failure',input_state_id=stem+'_UPTAKE_WEIGHED',output_state_id=sid,operation_id=opid,relation='reported_exception_for_this_membrane',does_not_fill_missing_quantitative_cell=True)
 orders.extend([dict(id='WEIGH_BEFORE_BOILING_FAILURE',kind='order',before_operation_id='UPTAKE_WEIGH',after_operation_id=opid,scope=name,source_fragment='uptake',relation='dry_reference_weighing_precedes_water_exposure',not_sequence_between_temperatures=True),dict(id='DRY_BEFORE_WEIGH',kind='order',before_operation_pointer=methods['uptake_drying'][0]['pointer'],after_operation_id='UPTAKE_WEIGH',scope=[a['identity'] for a in p['existing_individual_polymer_inputs']],source_fragment='uptake',relation='dry_reference_then_weigh')])
 for key in ['acid','sodium']:
  ionic=f['ionic_TGA']['captures'][key]['value_raw'];sid='TGA_'+key.upper()
  state(sid,'SPAEK-NA '+ionic+' group','after independent TGA moisture-removal conditioning','TGA specimen conditioned in air to 150°C, held 10 min and cooled to 90°C','ionic_TGA',ionic_form=ionic,assay='TGA',conditioning_operation_pointers=[a['pointer'] for a in methods['TGA_conditioning']],per_polymer_cartesian_expansion_not_inferred=True)
  binding(sid,'ionic_TGA',output_state_id=sid,operation_pointers=[a['pointer'] for a in methods['TGA_conditioning']],relation='independent_ionic_form_TGA_group_conditioning',ion_conversion_not_inferred=True)
 control=p['unsulfonated_control_anchor'];state('UNSULFONATED_PHASE',control['identity'],'unsulfonated control','semicrystalline polymer','phase',original_sample_identity_pointer=control['pointer'],property_values_not_copied=True)
 binding('UNSULFONATED_PHASE','phase',output_state_id='UNSULFONATED_PHASE',input_sample_identity_pointer=control['pointer'],relation='phase_of_explicit_control')
 parameters=[dict(id='CONDUCTIVITY_DIAMETER',kind='parameter',role='conductivity film diameter',value_raw=f['conductivity']['captures']['diameter']['value_raw'],unit_normalized='mm',operation_pointer=methods['conductivity_hydration'][0]['pointer'],assay='transverse proton conductivity',scope=[a['identity'] for a in p['existing_individual_polymer_inputs']],source_fragment='conductivity')]
 return dict(operations=ops,states=states,bindings=bindings,orders=orders,parameters=parameters,state_index=index,actual_pair_index=pairs_index,saved_fragments=f,existing_individual_polymer_inputs=deepcopy(p['existing_individual_polymer_inputs']),existing_casting_state_prototypes=deepcopy(p['existing_casting_state_prototypes']),existing_method_prototypes=deepcopy(methods),unsulfonated_control_anchor=deepcopy(control),actual_uptake_pairs=deepcopy(p['actual_uptake_pairs']),property_point_origin=deepcopy(p['property_source']),source_approval_path=approval['path'],source_approval_sha256=approval['sha256'],original_property_values_and_bindings_unchanged=True,new_pdf_information_extracted=0)


def main():
 parentpath=OUT/'process_relation_trial_019/freeze.json';parent=read(parentpath);approval,=read(OUT/'saved_membrane_specimen_links_recovery/source_reviews/manifest.json')['papers'];assert sha(approval['path'])==approval['sha256'];review=read(approval['path']);assert sha(review['proposal_path'])==review['proposal_sha256'];packet=read(review['proposal_path']);rows=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no']==approval['reference_no']:
   new=read(p['candidate_path']);assert EXTENSION not in new;new[EXTENSION]=[build(packet['proposals'][0],approval)];dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new);row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  rows.append(row)
 save(TRIAL/'freeze.json',dict(version=TRIAL.name,parent_trial='process_relation_trial_019',parent_trial_freeze_sha256=sha(parentpath),baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),proposal_generation_code_sha256=sha(OUT/'propose_saved_membrane_specimen_links.py'),papers=rows,papers_total=101,changed_papers_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows),property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,stable_workflow_release=False,external_api_calls=0));print(dict(papers=101,changed_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows)))


if __name__=='__main__':main()
