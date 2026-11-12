"""Append source-scoped process context in a separate candidate, no property edits."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha

TRIAL=OUT/'process_relation_trial_007'
EXTENSION='process_saved_quinolate_context_recovery'


def build_groups(proposals,a):
 groups=[]
 for r in proposals:
  f=r['captures'];v=lambda k:f[k]['value_raw'];operations=[];states=[];parameters=[];bindings=[]
  if r['method']=='protected_ligand_outcome':
   parameters=[dict(id='METHOXY_CLEAVAGE',kind='parameter',role='reported outcome of protected quinoline ligand attachment',bond=v('bond'),change=v('change'),product=v('product'),byproduct=v('byproduct'),source_capture_keys=['bond','change','product','byproduct'])]
   bindings=[dict(id='PROTECTED_SCOPE_'+str(i),kind='binding',qualification_id='METHOXY_CLEAVAGE',existing_ligand_path=t['path'],samples=t['samples'],operation_id=t['operation_id'],does_not_apply_to_methoxyphenyl_substituent_on_hydroxy_ligand=True) for i,t in enumerate(r['existing_targets'])]
  elif r['method']=='gpc_mobile_phase':
   operations=[dict(id='GPC_SALT_MEDIUM',kind='operation',name='Add the reported salt to the GPC solvent for the NMe2 specimen',parameters=[dict(role='mobile-phase additive',value_raw='['+v('salt')+']Br',source_capture='salt'),dict(role='mass-fraction loading',value_raw=v('loading'),source_capture='loading'),dict(role='mobile-phase solvent',value_raw='THF',source_quote='medium_method_quote')])]
   states=[dict(id='NME2_SALTED_GPC',kind='state',sample=v('sample'),state='GPC specimen eluting as the reported '+v('outcome')+' with the salt-containing THF mobile phase',monomodal_source_capture='outcome',is_analytical_specimen_not_synthetic_doping=True)]
   bindings=[dict(id='GPC_SPECIMEN_SCOPE',kind='binding',operation_id='GPC_SALT_MEDIUM',existing_polymer_state_path=r['existing_targets'][0]['path'],sample=v('sample'),output_state='NME2_SALTED_GPC',no_new_molecular_weight_record_created=True)]
  else:
   parameters=[dict(id='PHOTO_EXCITATION',kind='parameter',role='excitation for Figure3 solution photographs only',value_raw=v('wavelength'),unit_raw=v('unit'),method=v('excitation'),source_capture_keys=['wavelength','unit','excitation'])]
   bindings=[dict(id='PHOTO_SCOPE_'+str(i),kind='binding',qualification_id='PHOTO_EXCITATION',existing_state_path=t['path'],existing_state_id=t['state_id'],sample=t['identity'],not_photocrosslinking=True,not_absorption_maximum_excitation_for_spectra=True) for i,t in enumerate(r['existing_targets'])]
  groups.append(dict(proposal_id=r['proposal_id'],method=r['method'],operations=operations,parameters=parameters,states=states,orders=[],bindings=bindings,
   saved_quote=r['existing_quote'],literal_captures=r['captures'],medium_method_quote=r.get('medium_method_quote'),source_approval_path=a['path'],source_approval_sha256=a['sha256'],unknown_conditions_not_filled=True,new_pdf_information_extracted=0))
 return groups


def main():
 pp=OUT/'process_relation_trial_006/freeze.json';parent=read(pp);approved={a['reference_no']:a for a in read(OUT/'saved_quinolate_context_recovery/source_reviews/manifest.json')['papers']};rows=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no'] in approved:
   a=approved[p['reference_no']];assert sha(a['path'])==a['sha256'];approval=read(a['path']);assert sha(approval['proposal_path'])==approval['proposal_sha256'];packet=read(approval['proposal_path']);old=read(p['candidate_path']);new=deepcopy(old);new[EXTENSION]=build_groups(packet['proposals'],a)
   assert len(new[EXTENSION])==3 and all(new[k]==v for k,v in old.items());dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new);row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  rows.append(row)
 save(TRIAL/'freeze.json',dict(version='process_relation_trial_007',parent_trial='process_relation_trial_006',parent_trial_freeze_sha256=sha(pp),baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),proposal_generation_code_sha256=sha(OUT/'propose_saved_quinolate_contexts.py'),papers=rows,papers_total=101,cumulative_changed_papers=sum(bool(p.get('changed_from_parent')) for p in rows),changed_papers_this_round=1,frozen_original_outputs_modified=False,property_content_or_bindings_modified=False,existing_candidate_process_fields_revised=0,reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,all101_scientific_targets_proven=False,stable_workflow_release=False,external_api_calls=0))
 print({'papers':101,'changed_this_round':1,'cumulative_changed_papers':sum(bool(p.get('changed_from_parent')) for p in rows)})

if __name__=='__main__':main()
