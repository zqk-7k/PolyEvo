from copy import deepcopy
from prepare_audit import OUT,read,save,sha

TRIAL=OUT/'process_relation_trial_013'
EXTENSION='process_saved_polyester_thermal_variants_recovery'


def build(r,a):
 f=r['fragments'];v=lambda g,k:f[g]['captures'][k]['value_raw'];ops=[];states=[];materials=[];bindings=[];measurements=[];label=v('captions6and7','label')
 def par(role,g,k,unit=None):return dict(role=role,value_raw=v(g,k),unit_raw=v(g,unit) if unit else None,source_fragment=g,source_capture=k)
 def temperature(role,g,k):return dict(role=role,value_raw=v(g,k),unit_raw='°C',source_fragment=g,source_capture=k,unit_basis='explicit degree C in the same saved quotation')
 def case(ident,sample,target,name,input_kind,input_text,output_text,params,measurement,observation=None):
  inode=ident+'_INPUT';onode=ident+'_PREPARED';node=dict(id=inode,kind=input_kind,sample=sample,state=input_text) if input_kind=='state' else dict(id=inode,kind=input_kind,name=sample,phase_not_recovered=True)
  (states if input_kind=='state' else materials).append(node);states.append(dict(id=onode,kind='state',sample=sample,state=output_text,thermal_variant=ident,phase_fraction_not_inferred=True))
  ops.append(dict(id=ident,kind='operation',sample=sample,name=name,inputs=[inode],outputs=[onode],parameters=params,thermal_variant=ident))
  mid=ident+'_DSC';measurements.append(dict(id=mid,kind='measurement_context_annotation',sample=sample,prepared_state=onode,measurement=measurement,observed_response=observation,processing_operation_not_created_for_pure_measurement=True,scan_rate_not_specimen_cooling_rate=True))
  bindings.append(dict(id='SCOPE_'+ident,kind='binding',sample=sample,operation_id=ident,input_nodes=[inode],output_states=[onode],measurement_annotation=mid,existing_material_identity_target=target,relation='source-named material identity and history, not physical batch transfer',physical_batch_or_replica_identity_unknown=True))
 case('DRY_6D',label,r['thermal_material_target'],v('dry_quench_response','drying'),'state','polymer after '+v('dry_quench_response','initial'),'polymer after the reported drying of precipitated material',[temperature('drying temperature','dry_quench_response','dry_temperature')],'DSC after the reported precipitation and drying',v('dry_quench_response','response'))
 case('F6_A',label,r['thermal_material_target'],v('captions6and7','quench_action'),'state',v('captions6and7','quench_input'),'quenched specimen from the reported isotropic melt',[],'Figure 6A heating of the quenched specimen',v('dry_quench_response','response'))
 for tag,key in [('F6_B','b'),('F6_C','c')]:case(tag,label,r['thermal_material_target'],v('captions6and7','cool_action_'+key),'state','melt at the separately reported initial temperature','melt-cooled specimen; crystallinity not assigned',[temperature('initial melt temperature','captions6and7','melt_'+key),par('specimen cooling rate','captions6and7','rate_'+key,'rate_'+key+'_unit')],'Figure 6'+key.upper()+' heating after the specified cooling history')
 for tag,key,response in [('F7_A','a','response_high'),('F7_B','b','response_high'),('F7_C','c','response_low')]:case(tag,label,r['thermal_material_target'],v('captions6and7','anneal_action_'+key),'material_identity_annotation',None,'annealed specimen under this source-labelled condition',[temperature('annealing temperature','captions6and7','temperature_'+key),par('annealing duration','captions6and7','duration_'+key,'duration_'+key+'_unit')],'Figure 7'+key.upper()+' heating after this annealing history',v(response,'response'))
 methodlabel=v('caption9','label')+' ('+v('caption9','method')+')';case('F9_C',methodlabel,r['method_specific_target'],v('caption9','action'),'material_identity_annotation',None,'method-specific polymer after the Figure 9C annealing',[temperature('annealing temperature','caption9','temperature'),par('annealing duration','caption9','duration','duration_unit')],'Figure 9C '+v('caption9','measurement'))
 return dict(proposal_id=r['proposal_id'],materials=materials,operations=ops,parameters=[],states=states,orders=[],bindings=bindings,measurement_annotations=measurements,saved_fragments=f,existing_property_anchors=r['existing_property_anchors'],source_approval_path=a['path'],source_approval_sha256=a['sha256'],different_figure_labels_are_not_consecutive_holds=True,physical_batch_or_replica_identity_unknown=True,scan_rates_retained_as_pure_measurement_context_not_process_parameters=True,quench_temperature_and_medium_not_recovered=True,new_pdf_information_extracted=0)


def main():
 pp=OUT/'process_relation_trial_012/freeze.json';parent=read(pp);approved={x['reference_no']:x for x in read(OUT/'saved_polyester_thermal_variants_recovery/source_reviews/manifest.json')['papers']};rows=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no'] in approved:
   a=approved[p['reference_no']];assert sha(a['path'])==a['sha256'];ap=read(a['path']);assert sha(ap['proposal_path'])==ap['proposal_sha256'];r=read(ap['proposal_path'])['proposals'][0];old=read(p['candidate_path']);new=deepcopy(old);new[EXTENSION]=[build(r,a)];dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new);row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  rows.append(row)
 save(TRIAL/'freeze.json',dict(version='process_relation_trial_013',parent_trial='process_relation_trial_012',parent_trial_freeze_sha256=sha(pp),baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),proposal_generation_code_sha256=sha(OUT/'propose_saved_polyester_thermal_variants.py'),papers=rows,papers_total=101,cumulative_changed_papers=sum(bool(p.get('changed_from_parent')) for p in rows),changed_papers_this_round=1,property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,existing_process_fields_revised=0,reference_answers_or_scores_used_as_prediction_inputs=False,reference_seen_previously_during_error_diagnosis=True,new_pdf_information_extracted=0,stable_workflow_release=False,external_api_calls=0));print({'papers':101,'changed_this_round':1,'cumulative_changed_papers':sum(bool(p.get('changed_from_parent')) for p in rows)})

if __name__=='__main__':main()
