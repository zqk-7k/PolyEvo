from copy import deepcopy
from prepare_audit import OUT,read,save,sha

TRIAL=OUT/'process_relation_trial_008'
EXTENSION='process_saved_polyaddition_workup_recovery'


def build(r,a):
 f=r['fragments'];v=lambda group,key:f[group]['captures'][key]['value_raw'];label=r['label']
 def par(role,g,k,unit=None):return dict(role=role,value_raw=v(g,k),unit_raw=v(g,unit) if unit else None,source_fragment=g,source_capture=k)
 ops=[dict(id='HOLD_COLD',kind='operation',name='Hold the named polyaddition mixture at the reported cold temperature',sample=label,inputs=['REACTION_FEED'],outputs=['AFTER_COLD'],parameters=[par('temperature','cold','temperature','temperature_unit'),par('duration','cold','duration','duration_unit'),par('atmosphere','continuation','atmosphere')]),
  dict(id='HOLD_RT',kind='operation',name='Continue the same named polyaddition at room temperature',sample=label,inputs=['AFTER_COLD'],outputs=['AFTER_RT'],parameters=[par('temperature','continuation','temperature'),par('duration','continuation','duration','duration_unit'),par('atmosphere','continuation','atmosphere')]),
  dict(id='FILTER_PRODUCT',kind='operation',name=v('workup','collection'),sample=label,inputs=['PRECIPITATED_PRODUCT'],outputs=['FILTERED_PRODUCT'],parameters=[]),
  dict(id='DRY_PRODUCT',kind='operation',name=v('workup','drying'),sample=label,inputs=['FILTERED_PRODUCT'],outputs=['DRIED_PRODUCT'],parameters=[par('temperature','workup','temperature','temperature_unit'),par('environment','workup','pressure'),par('isolated product mass','workup','mass','mass_unit'),dict(role='reported isolated yield in typical procedure only',value_raw=v('workup','yield'),unit_raw='%',source_fragment='workup',source_capture='yield',does_not_replace_other_reported_tabular_yield=True)])]
 states=[dict(id='REACTION_FEED',kind='state',sample=label,state='the reported reaction mixture entering the hold program',charging_recipe_not_recovered=True),dict(id='AFTER_COLD',kind='state',sample=label,state='named reaction mixture after the recorded cold hold'),dict(id='AFTER_RT',kind='state',sample=label,state='same reaction mixture after subsequent room-temperature polyaddition under argon'),dict(id='PRECIPITATED_PRODUCT',kind='state',sample=label,state=v('workup','input_state')+' '+v('workup','polymer'),unrecovered_dilution_and_precipitation_operations_not_filled=True),dict(id='FILTERED_PRODUCT',kind='state',sample=label,state='precipitated polymer collected by filtration'),dict(id='DRIED_PRODUCT',kind='state',sample=label,state=v('workup','state'),stage='after the reported reduced-pressure drying',source_fragment='workup',source_capture='state')]
 orders=[dict(id='COLD_BEFORE_RT',kind='order',before='HOLD_COLD',after='HOLD_RT',relation='precedes',basis='explicit linked continuation, not array order'),dict(id='FILTER_BEFORE_DRY',kind='order',before='FILTER_PRODUCT',after='DRY_PRODUCT',relation='precedes',basis='same sentence explicitly reports collection then drying')]
 bindings=[dict(id='SCOPE_'+o['id'],kind='binding',sample=label,operation_id=o['id'],input_states=o['inputs'],output_states=o['outputs'],scope='this named typical procedure only') for o in ops]
 bindings.append(dict(id='PRODUCT_IDENTITY',kind='binding',sample=label,output_state='DRIED_PRODUCT',existing_sample_targets=r['existing_sample_targets'],relation='reported_material_identity_not_new_physical_batch_transfer'))
 return dict(proposal_id=r['proposal_id'],label=label,operations=ops,parameters=[],states=states,orders=orders,bindings=bindings,saved_fragments=f,existing_property_anchors=r['existing_property_anchors'],source_approval_path=a['path'],source_approval_sha256=a['sha256'],unrecovered_intervening_workup_not_replaced_with_direct_order=True,new_pdf_information_extracted=0)


def main():
 pp=OUT/'process_relation_trial_007/freeze.json';parent=read(pp);approved={x['reference_no']:x for x in read(OUT/'saved_polyaddition_workup_recovery/source_reviews/manifest.json')['papers']};rows=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no'] in approved:
   a=approved[p['reference_no']];assert sha(a['path'])==a['sha256'];ap=read(a['path']);assert sha(ap['proposal_path'])==ap['proposal_sha256'];packet=read(ap['proposal_path']);old=read(p['candidate_path']);new=deepcopy(old);new[EXTENSION]=[build(packet['proposals'][0],a)];dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new);row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  rows.append(row)
 save(TRIAL/'freeze.json',dict(version='process_relation_trial_008',parent_trial='process_relation_trial_007',parent_trial_freeze_sha256=sha(pp),baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),proposal_generation_code_sha256=sha(OUT/'propose_saved_polyaddition_workup.py'),papers=rows,papers_total=101,cumulative_changed_papers=sum(bool(p.get('changed_from_parent')) for p in rows),changed_papers_this_round=1,property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,existing_candidate_process_fields_revised=0,reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,stable_workflow_release=False,external_api_calls=0));print({'papers':101,'changed_this_round':1,'cumulative_changed_papers':sum(bool(p.get('changed_from_parent')) for p in rows)})

if __name__=='__main__':main()
