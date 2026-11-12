"""Add per-row viscosity state using only the saved table and its old footnote."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha

TRIAL=OUT/'process_relation_trial_021'
EXTENSION='process_saved_table_viscosity_specimens_recovery'


def build(p,approval):
 states=[];bindings=[];index=[];caps=p['footnote_captures']
 for r in p['parsed_rows']:
  if 'existing_identity_anchor' not in r:continue
  a=r['existing_identity_anchor'];sid=a['id']+'_VISCOSITY';states.append(dict(id=sid,kind='state',identity=a['identity'],synthesis_monomer_concentration_raw=r['monomer_concentration'],synthesis_monomer_concentration_unit='%',stage='during inherent-viscosity measurement',state='reported polymer solution for viscosity',medium=caps['medium']['value_raw'],polymer_solution_concentration_raw=caps['polymer_concentration']['value_raw'],polymer_solution_concentration_unit='g/dL',measurement_temperature_raw=caps['measurement_temperature']['value_raw'],measurement_temperature_unit='°C',dissolution_temperature_unknown=True,LiCl_dose_not_generalized=True,synthesis_additive_not_inferred_from_measurement_medium=True,original_sample_identity_pointer=a['pointer'],saved_table_row_index=r['saved_row_index'],reference_to_numeric_viscosity_cell=r['cells'][5],actual_numeric_viscosity_record_not_rewritten=True,physical_specimen_allocation_unspecified=True))
  bindings.append(dict(id='B_'+sid,kind='binding',input_sample_identity_pointer=a['pointer'],output_state_id=sid,relation='footnote_solution_condition_applies_to_this_numeric_table_row',scope=dict(polymer=r['polymer'],R1=r['R1'],R2=r['R2'],synthesis_monomer_concentration_raw=r['monomer_concentration']),physical_batch_or_dissolution_operation_not_inferred=True));index.append(dict(saved_table_row_index=r['saved_row_index'],state_index=len(states)-1,binding_index=len(bindings)-1,polymer=r['polymer'],R1=r['R1'],R2=r['R2'],monomer_concentration=r['monomer_concentration']))
 return dict(operations=[],parameters=[],orders=[],states=states,bindings=bindings,actual_numeric_row_index=index,saved_table_quote=deepcopy(p['saved_table_quote']),saved_text_sha256=p['text_sha256'],footnote_captures=deepcopy(caps),parsed_saved_rows=deepcopy(p['parsed_rows']),existing_generic_viscosity_anchor=deepcopy(p['existing_generic_viscosity_anchor']),generic_anchor_is_not_evidence_for_global_two_percent_LiCl=True,source_approval_path=approval['path'],source_approval_sha256=approval['sha256'],original_property_values_and_bindings_unchanged=True,new_pdf_information_extracted=0)


def main():
 parentpath=OUT/'process_relation_trial_020/freeze.json';parent=read(parentpath);approval,=read(OUT/'saved_table_viscosity_specimens_recovery/source_reviews/manifest.json')['papers'];assert sha(approval['path'])==approval['sha256'];review=read(approval['path']);assert sha(review['proposal_path'])==review['proposal_sha256'];packet=read(review['proposal_path']);rows=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no']==approval['reference_no']:
   new=read(p['candidate_path']);assert EXTENSION not in new;new[EXTENSION]=[build(packet['proposals'][0],approval)];dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new);row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  rows.append(row)
 save(TRIAL/'freeze.json',dict(version=TRIAL.name,parent_trial='process_relation_trial_020',parent_trial_freeze_sha256=sha(parentpath),baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),proposal_generation_code_sha256=sha(OUT/'propose_saved_table_viscosity_specimens.py'),papers=rows,papers_total=101,changed_papers_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows),property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,stable_workflow_release=False,external_api_calls=0));print(dict(papers=101,changed_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows)))


if __name__=='__main__':main()
