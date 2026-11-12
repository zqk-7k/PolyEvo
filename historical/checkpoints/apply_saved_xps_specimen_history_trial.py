"""Link actual PDMS exposure specimens to their own assay preparation history."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha

TRIAL=OUT/'process_relation_trial_022'
EXTENSION='process_saved_xps_specimen_history_recovery'


def build(p,approval):
 states=[];ops=[];bindings=[];orders=[];index=[];methods=p['existing_method_prototypes'];caps=p['post_exposure_captures']
 for assay,pairs in [('XPS',p['actual_pairs']),('CONTACT_ANGLE',p['contact_angle_actual_pairs'])]:
  for pair in pairs:
   ident=assay+'_'+pair['identity'].replace('.','_')+'_'+pair['exposure'].upper()+'_'+pair['duration_raw'].replace('.','_')+pair['duration_unit'];s0=ident+'_EXPOSED';opid='EXPOSE_'+ident;provenance='xps_actual_rows' if assay=='XPS' else 'contact_angle_actual_panels'
   op=dict(id=opid,kind='operation',name=pair['exposure']+' surface exposure for '+assay+' specimen',scope=pair['identity'],assay=assay,existing_method_prototype_pointer=methods[pair['exposure']]['pointer'],input_prepared_network_pointer=p['existing_prepared_network_anchor']['pointer'],input_network_code=pair['identity'],output_state_id=s0,parameters=[dict(role='actual exposure duration',value_raw=pair['duration_raw'],unit_normalized=pair['duration_unit'])],source_scope=provenance,alternative_times_not_sequential_exposures=True)
   if assay=='XPS':op['actual_reported_property_point_anchors']=deepcopy(pair['actual_reported_point_anchors'])
   ops.append(op);state_index=len(states);states.append(dict(id=s0,kind='state',identity=pair['identity'],stage='immediately after '+pair['duration_raw']+pair['duration_unit']+' '+pair['exposure']+' exposure',state=pair['exposure']+'-exposed PDMS surface',assay=assay,operation_id=opid,source_scope=provenance,recovery_aging_history_not_inferred=True));bindings.append(dict(id='B_'+s0,kind='binding',input_sample_identity_pointer=p['existing_network_identity_anchor']['pointer'],input_prepared_network_pointer=p['existing_prepared_network_anchor']['pointer'],input_network_code=pair['identity'],output_state_id=s0,operation_id=opid,relation='actual_sample_exposure_assay_method_application',source_scope=provenance,physical_transfer_between_assays_not_asserted=True));record=dict(identity=pair['identity'],exposure=pair['exposure'],duration_raw=pair['duration_raw'],duration_unit=pair['duration_unit'],assay=assay,exposure_operation_index=len(ops)-1,exposed_state_index=state_index)
   if assay=='XPS':
    s1=ident+'_CHLOROFORM_EXTRACTED';s2=ident+'_VACUUM_DEGASSED'
    for sid,prev,stage,text,method in [(s1,s0,'after post-exposure extraction','exposed specimen after '+caps['duration']['value_raw']+' h Soxhlet extraction in '+caps['solvent']['value_raw'],'extraction'),(s2,s1,'before XPS','exposed and CHCl3-extracted specimen subsequently degassed in '+caps['environment']['value_raw'],'degassing')]:
     states.append(dict(id=sid,kind='state',identity=pair['identity'],stage=stage,state=text,assay=assay,existing_method_prototype_pointer=methods[method]['pointer'],exposure_operation_id=opid,source_scope='xps_preparation',initial_hexane_preparation_not_replaced=True));bindings.append(dict(id='B_'+sid,kind='binding',input_state_id=prev,output_state_id=sid,operation_pointer=methods[method]['pointer'],exposure_operation_id=opid,scope=pair['identity'],relation='within_actual_XPS_specimen_preparation',source_scope='xps_preparation'))
    record.update(extracted_state_index=len(states)-2,degassed_state_index=len(states)-1)
    orders.extend([dict(id='EXPOSE_THEN_EXTRACT_'+ident,kind='order',before_operation_id=opid,after_operation_pointer=methods['extraction']['pointer'],scope=pair['identity'],assay=assay,source_scope='xps_preparation',not_initial_hexane_extraction=True),dict(id='EXTRACT_THEN_DEGAS_'+ident,kind='order',before_operation_pointer=methods['extraction']['pointer'],after_operation_pointer=methods['degassing']['pointer'],scope=pair['identity'],assay=assay,exposure_operation_id=opid,source_scope='xps_preparation')])
   index.append(record)
 return dict(operations=ops,states=states,bindings=bindings,orders=orders,parameters=[],specimen_condition_index=index,saved_post_exposure_quote=deepcopy(p['post_exposure_quote']),saved_post_exposure_quote_sha256=p['text_sha256'],post_exposure_captures=deepcopy(caps),saved_contact_angle_panel_quote=deepcopy(p['contact_angle_panel_quote']),saved_contact_angle_panel_quote_sha256=p['contact_angle_panel_quote_sha256'],contact_angle_panel_captures=deepcopy(p['contact_angle_panel_captures']),actual_XPS_pairs=deepcopy(p['actual_pairs']),actual_contact_angle_pairs=deepcopy(p['contact_angle_actual_pairs']),existing_method_prototypes=deepcopy(methods),existing_network_identity_anchor=deepcopy(p['existing_network_identity_anchor']),existing_prepared_network_anchor=deepcopy(p['existing_prepared_network_anchor']),property_point_origin=deepcopy(p['property_source']),source_approval_path=approval['path'],source_approval_sha256=approval['sha256'],original_property_values_and_bindings_unchanged=True,new_pdf_information_extracted=0)


def main():
 parentpath=OUT/'process_relation_trial_021/freeze.json';parent=read(parentpath);approval,=read(OUT/'saved_xps_specimen_history_recovery/source_reviews/manifest.json')['papers'];assert sha(approval['path'])==approval['sha256'];review=read(approval['path']);assert sha(review['proposal_path'])==review['proposal_sha256'];packet=read(review['proposal_path']);rows=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no']==approval['reference_no']:
   new=read(p['candidate_path']);assert EXTENSION not in new;new[EXTENSION]=[build(packet['proposals'][0],approval)];dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new);row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  rows.append(row)
 save(TRIAL/'freeze.json',dict(version=TRIAL.name,parent_trial='process_relation_trial_021',parent_trial_freeze_sha256=sha(parentpath),baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),proposal_generation_code_sha256=sha(OUT/'propose_saved_xps_specimen_history.py'),papers=rows,papers_total=101,changed_papers_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows),property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,stable_workflow_release=False,external_api_calls=0));print(dict(papers=101,changed_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows)))


if __name__=='__main__':main()
