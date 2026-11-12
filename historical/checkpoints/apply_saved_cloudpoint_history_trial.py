"""Append source-verified saved heating history without editing old claims."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha

TRIAL=OUT/'process_relation_trial_017'
EXTENSION='process_saved_cloudpoint_history_recovery'


def build(proposal,approval,old):
 fragments=deepcopy(proposal['fragments']);caps=fragments['lcst_method']['captures'];graph=old['process_graph'];eligible=[(i,x) for i,x in enumerate(graph['states']) if x.get('scope')=='individual' and x.get('purpose')=='LCST' and x.get('state')=='aqueous solution diluted to selected concentration'];states=[];bindings=[]
 for i,x in eligible:
  output='CLOUD_'+x['id'];inp='/process_graph/states/'+str(i);states.append(dict(id=output,kind='state',identity=x['identity'],stage='slow oil-bath heating through cloud point',state=caps['transition']['value_raw'],medium=caps['medium']['value_raw'],input_state_pointer=inp,source_fragments=['lcst_method'],numeric_cloudpoint_not_added=True));bindings.append(dict(id='HEAT_'+x['id'],kind='binding',operation_id='LCST_HEAT',input_state_pointer=inp,output_states=[output],scope=x['identity'],source_fragments=['lcst_method'],separate_specimens_not_pooled=True))
 operation=dict(id='LCST_HEAT',kind='operation',name=caps['heating']['value_raw'],input_state_pointers=[b['input_state_pointer'] for b in bindings],output_states=[s['id'] for s in states],scope=[s['identity'] for s in states],parameters=[dict(role=role,value_raw=caps[key]['value_raw'],unit_raw=None,source_fragment='lcst_method',source_capture=key) for role,key in [('heating method','heating'),('medium','medium'),('observed endpoint','transition')]],source_fragments=['lcst_method'],separate_specimens_not_pooled=True,numeric_temperature_rate_and_pressure_unknown=True)
 before=next(i for i,x in enumerate(graph['operations']) if x['id']=='water_dilute');orders=[dict(id='DILUTION_THEN_HEATING',kind='order',before_operation_pointer='/process_graph/operations/'+str(before),after_operation_id='LCST_HEAT',scope=[s['identity'] for s in states],relation='precedes_within_each_reported_LCST_method_application',source_fragments=['lcst_method'])]
 return dict(states=states,operations=[operation],bindings=bindings,orders=orders,saved_fragments=fragments,source_approval_path=approval['path'],source_approval_sha256=approval['sha256'],conditional_states_not_promoted=True,original_property_values_and_bindings_unchanged=True,new_pdf_information_extracted=0)


def main():
 parentpath=OUT/'process_relation_trial_016/freeze.json';parent=read(parentpath);approved=read(OUT/'saved_cloudpoint_history_recovery/source_reviews/manifest.json')['papers'];assert len(approved)==1;approval=approved[0];assert sha(approval['path'])==approval['sha256'];review=read(approval['path']);assert sha(review['proposal_path'])==review['proposal_sha256'];packet=read(review['proposal_path']);rows=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no']==approval['reference_no']:
   old=read(p['candidate_path']);new=deepcopy(old);new[EXTENSION]=[build(packet['proposals'][0],approval,old)];dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new);row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  rows.append(row)
 save(TRIAL/'freeze.json',dict(version=TRIAL.name,parent_trial='process_relation_trial_016',parent_trial_freeze_sha256=sha(parentpath),baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),proposal_generation_code_sha256=sha(OUT/'propose_saved_cloudpoint_history.py'),papers=rows,papers_total=101,changed_papers_this_round=1,cumulative_changed_papers=sum(bool(p.get('changed_from_parent')) for p in rows),property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,stable_workflow_release=False,external_api_calls=0));print(dict(papers=len(rows),changed_this_round=1,cumulative_changed_papers=sum(bool(p.get('changed_from_parent')) for p in rows)))


if __name__=='__main__':main()
