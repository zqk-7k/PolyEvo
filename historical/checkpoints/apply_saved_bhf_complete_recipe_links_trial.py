"""Turn two complete existing recipe descriptions into scoped process records."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha

TRIAL=OUT/'process_relation_trial_026'
EXTENSION='process_saved_bhf_complete_recipe_links_recovery'


def build(recipes,approval):
 ops=[];bindings=[]
 for r in recipes:
  c=r['captures'];oid='COPOLYCONDENSE_'+r['local_product_key'];parameters=[]
  for key,role,unit,subkey in [('diol_mass','diol mass','mg','diol'),('diol_amount','diol amount','mmol','diol'),('coupling_mass','coupling agent mass','g','coupling_agent'),('coupling_amount','coupling agent amount','mmol','coupling_agent'),('auxiliary_mass','auxiliary mass','mg','auxiliary'),('auxiliary_amount','auxiliary amount','mmol','auxiliary'),('solvent_volume','reaction solvent volume','mL','solvent')]:parameters.append(dict(role=role,value_raw=c[key]['value_raw'],unit_normalized=unit,substance_raw=c[subkey]['value_raw'],source_capture=key))
  parameters.extend([dict(role='reaction solvent',value_raw=c['solvent']['value_raw'],source_capture='solvent'),dict(role='reaction temperature description',value_raw=c['temperature']['value_raw'],source_capture='temperature'),dict(role='reaction duration',value_raw=c['duration']['value_raw'],unit_normalized='h',source_capture='duration'),dict(role='acid feed molar ratio',value_raw=c['feed_ratio']['value_raw'],ordered_components=[c['first_acid']['value_raw'],c['second_acid']['value_raw']],unit_normalized='molar ratio',source_capture='feed_ratio')])
  ops.append(dict(id=oid,kind='operation',name='copolycondense BHF with mixed carboxylic acids using its own saved complete preparation',scope=r['local_product_key'],input_materials_raw=[c['diol']['value_raw'],c['first_acid']['value_raw'],c['second_acid']['value_raw']],output_sample_identity_pointer=r['existing_sample_pointer'],parameters=parameters,source_recipe_index=len(ops),conditions_apply_to_this_saved_row_only=True))
  bindings.append(dict(id='B_'+oid,kind='binding',operation_id=oid,output_sample_identity_pointer=r['existing_sample_pointer'],source_table='T3',source_row_label=r['row_label'],relation='existing_native_complete_recipe_belongs_to_this_saved_table_row',source_recipe_index=len(bindings),same_number_in_other_tables_not_same_sample=True))
 return dict(operations=ops,parameters=[],states=[],orders=[],bindings=bindings,saved_complete_recipes=deepcopy(recipes),no_conditions_transferred_to_unsaved_rows=True,source_approval_path=approval['path'],source_approval_sha256=approval['sha256'],original_property_values_and_bindings_unchanged=True,new_pdf_information_extracted=0)


def main():
 parentpath=OUT/'process_relation_trial_025/freeze.json';parent=read(parentpath);approval,=read(OUT/'saved_bhf_complete_recipe_links_recovery/source_reviews/manifest.json')['papers'];assert sha(approval['path'])==approval['sha256'];review=read(approval['path']);assert sha(review['proposal_path'])==review['proposal_sha256'];packet=read(review['proposal_path']);rows=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no']==approval['reference_no']:
   new=read(p['candidate_path']);assert EXTENSION not in new;new[EXTENSION]=[build(packet['proposals'],approval)];dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new);row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  rows.append(row)
 save(TRIAL/'freeze.json',dict(version=TRIAL.name,parent_trial='process_relation_trial_025',parent_trial_freeze_sha256=sha(parentpath),baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),proposal_generation_code_sha256=sha(OUT/'propose_saved_bhf_complete_recipe_links.py'),papers=rows,papers_total=101,changed_papers_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows),property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,stable_workflow_release=False,external_api_calls=0));print(dict(papers=101,changed_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows)))


if __name__=='__main__':main()
