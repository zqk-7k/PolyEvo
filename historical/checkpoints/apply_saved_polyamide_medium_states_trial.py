"""Append qualified, source-approved states from frozen old prediction evidence."""
from copy import deepcopy
import re
from prepare_audit import OUT,read,save,sha

TRIAL=OUT/'process_relation_trial_018'
EXTENSION='process_saved_polyamide_medium_states_recovery'


def build(group,approval):
 fragments=deepcopy(group['fragments']);caps=fragments['resistance']['captures'];states=[];bindings=[]
 for sample in group['existing_individual_polymer_inputs']:
  for key in ['medium_THF','medium_CHCl3','medium_alcohols']:
   raw=caps[key]['value_raw'];medium=re.sub(r'-\s*\n\s*','',raw);ident=sample['id']+'_'+key
   states.append(dict(id=ident,kind='state',identity=sample['identity'],input_state_pointer=sample['pointer'],stage='reported qualitative solvent resistance',medium=medium,medium_raw=raw,state=caps['response']['value_raw'],source_fragment='resistance',source_capture=key,qualitative_only=True,test_concentration_time_and_temperature_unknown=True,unspecified_alcohol_class_not_expanded=True))
   bindings.append(dict(id='B_'+ident,kind='binding',input_state_pointer=sample['pointer'],output_states=[ident],relation='reported_material_identity_and_medium_response',scope=sample['identity'],source_fragment='resistance',physical_specimen_transfer_not_asserted=True))
 phase=fragments['negative_phase']['captures'];states.append(dict(id='OBSERVED_NO_LYOTROPIC_SYSTEM',kind='state',identity='reported polyamide/solvent systems',input_state_pointers=[x['pointer'] for x in group['existing_individual_polymer_inputs']],stage=phase['scope']['value_raw'],state=phase['negative_phase']['value_raw'],source_fragment='negative_phase',reported_observation_only=True,all_possible_polymer_solvent_combinations_not_asserted=True))
 bindings.append(dict(id='B_OBSERVED_NO_LYOTROPIC_SYSTEM',kind='binding',input_state_pointers=[x['pointer'] for x in group['existing_individual_polymer_inputs']],output_states=['OBSERVED_NO_LYOTROPIC_SYSTEM'],relation='reported_observation_scope',scope='actually manipulated solutions of the reported polyamides',source_fragment='negative_phase',physical_specimen_transfer_not_asserted=True,not_cartesian_expansion_of_unreported_tests=True))
 return dict(states=states,operations=[],parameters=[],orders=[],bindings=bindings,saved_fragments=fragments,source_approval_path=approval['path'],source_approval_sha256=approval['sha256'],original_property_values_and_bindings_unchanged=True,new_pdf_information_extracted=0)


def main():
 parentpath=OUT/'process_relation_trial_017/freeze.json';parent=read(parentpath);approval,=read(OUT/'saved_polyamide_medium_states_recovery/source_reviews/manifest.json')['papers'];assert sha(approval['path'])==approval['sha256'];review=read(approval['path']);assert sha(review['proposal_path'])==review['proposal_sha256'];packet=read(review['proposal_path']);rows=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no']==approval['reference_no']:
   new=read(p['candidate_path']);assert EXTENSION not in new;new[EXTENSION]=[build(packet['proposals'][0],approval)];dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new);row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  rows.append(row)
 save(TRIAL/'freeze.json',dict(version=TRIAL.name,parent_trial='process_relation_trial_017',parent_trial_freeze_sha256=sha(parentpath),baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),proposal_generation_code_sha256=sha(OUT/'propose_saved_polyamide_medium_states.py'),papers=rows,papers_total=101,changed_papers_this_round=1,cumulative_changed_papers=sum(bool(p.get('changed_from_parent')) for p in rows),property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,stable_workflow_release=False,external_api_calls=0));print(dict(papers=len(rows),changed_this_round=1,cumulative_changed_papers=sum(bool(p.get('changed_from_parent')) for p in rows)))


if __name__=='__main__':main()
