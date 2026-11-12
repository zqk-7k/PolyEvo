"""Recover paired old table conditions and only explicitly soluble workup members."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha

TRIAL=OUT/'process_relation_trial_019'
EXTENSION='process_saved_polyester_schedule_recovery'


def build(proposal,approval):
 fragments=deepcopy(proposal['fragments']);rows=proposal['table_rows'];ops=[];states=[];bindings=[];condition_index=[]
 for row in rows:
  anchor=row['existing_sample_anchor']
  for j,entry in enumerate(row['condition_pairs']):
   ident='THERMAL_'+row['label']+'_'+str(j+1);pointer=anchor['pointer']
   ops.append(dict(id=ident,kind='operation',name='reported thermal polycondensation condition',scope=row['label'],input_sample_identity_pointer=pointer,parameters=[dict(role='reaction temperature',value_raw=entry['temperature_value'],unit_normalized=entry['temperature_unit_normalized'],source_cell=entry['temperature_cell']),dict(role='reported duration at this temperature',value_raw=entry['duration_raw'],unit_normalized=entry['duration_unit_normalized'],source_cell=entry['duration_cell'])],source_fragment='table',uninterpreted_source_tag=entry['uninterpreted_source_tag'],atmosphere_not_inferred_from_tag=True,temporal_order_not_asserted=True,identity_pointer_is_not_physical_reheating_of_isolated_product=True))
   bindings.append(dict(id='B_'+ident,kind='binding',operation_id=ident,input_sample_identity_pointer=pointer,scope=row['label'],relation='reported_reaction_condition_for_this_preparation',source_fragment='table',does_not_assert_common_batch_or_actual_specimen_reuse=True))
   condition_index.append(dict(label=row['label'],reported_entry_index=j,operation_pointer_index=len(ops)-1,tag=entry['uninterpreted_source_tag']))
 eligible=[r for r in rows if r['viscosity_indicator']['value_raw']!='Insol.'];caps=fragments['workup']['captures'];scope=[r['label'] for r in eligible]
 workup_specs=[('REDISSOLVE','dissolve resulting soluble polyester',[dict(role='solvent mixture',value_raw=caps['medium']['value_raw'],source_capture='medium'),dict(role='solvent volume ratio',value_raw=caps['ratio']['value_raw'],source_capture='ratio')]),('REPRECIPITATE','precipitate dissolved polyester',[dict(role='precipitant',value_raw=caps['precipitant']['value_raw'],source_capture='precipitant')]),('DRY','dry isolated polyester',[dict(role='drying temperature',value_raw=caps['dry_temperature']['value_raw'],unit_normalized='°C',source_capture='dry_temperature'),dict(role='drying pressure',value_raw=caps['dry_pressure']['value_raw'],unit_normalized='mbar',source_capture='dry_pressure')])]
 for opid,name,pars in workup_specs:ops.append(dict(id=opid,kind='operation',name=name,scope=scope,parameters=pars,source_fragment='workup',successful_solution_workup_does_not_apply_to_insoluble_row=True))
 for r in eligible:
  a=r['existing_sample_anchor'];previous=None
  for j,(opid,_,_) in enumerate(workup_specs):
   ident=r['label']+'_'+opid;state=dict(id=ident,kind='state',identity=r['label'],stage=['after solvent redissolution','after methanol precipitation','after 120°C/12mbar drying'][j],state=['polyester solution','methanol-precipitated polyester','dried isolated polyester'][j],operation_id=opid,source_fragment='workup',original_sample_identity_pointer=a['pointer'])
   if j==0:state['medium']=caps['medium']['value_raw'];state['solvent_volume_ratio']=caps['ratio']['value_raw']
   if j==1:state['precipitant']=caps['precipitant']['value_raw']
   if j==2:state.update(temperature_raw=caps['dry_temperature']['value_raw'],temperature_unit_normalized='°C',pressure_raw=caps['dry_pressure']['value_raw'],pressure_unit_normalized='mbar')
   states.append(state);bindings.append(dict(id='B_'+ident,kind='binding',operation_id=opid,input_state_id=previous,input_sample_identity_pointer=a['pointer'],output_state_id=ident,scope=r['label'],relation='explicit_saved_workup_material_flow' if previous else 'shared_workup_applies_to_confirmed_soluble_product',source_fragment='workup',distinct_polymers_not_pooled=True));previous=ident
 color=fragments['color']['captures'];high=fragments['context']['captures'];states.extend([dict(id='SELECTED_PRODUCT_COLOR',kind='state',identity='source-defined polyester products at the reported maximum-temperature limit',stage='after bulk polycondensation at '+color['temperature_scope']['value_raw'],state=color['color']['value_raw'],source_fragment='color',exact_color_of_each_polymer_not_inferred=True,solubility_not_generalized_from_color=True),dict(id='UNNAMED_HIGH_TEMPERATURE_TRIALS',kind='state',identity='unnamed preliminary polyester trials',stage='after condensation above '+high['maximum_temperature']['value_raw']+'°C',state=high['high_temperature_result']['value_raw'],source_fragment='context',not_assigned_to_selected_nine_table_rows=True)])
 bindings.extend([dict(id='B_COLOR_SCOPE',kind='binding',output_state_id='SELECTED_PRODUCT_COLOR',relation='reported_condition_and_product_appearance',scope='products at '+color['temperature_scope']['value_raw'],source_fragment='color'),dict(id='B_HIGH_TEMPERATURE_SCOPE',kind='binding',output_state_id='UNNAMED_HIGH_TEMPERATURE_TRIALS',relation='reported_preliminary_trial_scope',scope='unnamed trials above '+high['maximum_temperature']['value_raw']+'°C',source_fragment='context')])
 orders=[dict(id='SOLUTION_THEN_PRECIPITATE',kind='order',before_operation_id='REDISSOLVE',after_operation_id='REPRECIPITATE',scope=scope,relation='precedes_within_each_soluble_workup',source_fragment='workup'),dict(id='PRECIPITATE_THEN_DRY',kind='order',before_operation_id='REPRECIPITATE',after_operation_id='DRY',scope=scope,relation='precedes_within_each_soluble_workup',source_fragment='workup')]
 return dict(operations=ops,states=states,bindings=bindings,orders=orders,parameters=[],condition_index=condition_index,eligible_workup_labels=scope,source_tag_V_interpretation_unknown=True,no_thermal_schedule_edges_inferred=True,solubility_exception_preserved=True,saved_fragments=fragments,parsed_saved_table_rows=deepcopy(rows),source_approval_path=approval['path'],source_approval_sha256=approval['sha256'],original_property_values_and_bindings_unchanged=True,new_pdf_information_extracted=0)


def main():
 parentpath=OUT/'process_relation_trial_018/freeze.json';parent=read(parentpath);approval,=read(OUT/'saved_polyester_schedule_recovery/source_reviews/manifest.json')['papers'];assert sha(approval['path'])==approval['sha256'];review=read(approval['path']);assert sha(review['proposal_path'])==review['proposal_sha256'];packet=read(review['proposal_path']);rows=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no']==approval['reference_no']:
   new=read(p['candidate_path']);assert EXTENSION not in new;new[EXTENSION]=[build(packet['proposals'][0],approval)];dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new);row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  rows.append(row)
 save(TRIAL/'freeze.json',dict(version=TRIAL.name,parent_trial='process_relation_trial_018',parent_trial_freeze_sha256=sha(parentpath),baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),proposal_generation_code_sha256=sha(OUT/'propose_saved_polyester_schedule.py'),papers=rows,papers_total=101,changed_papers_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows),property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,stable_workflow_release=False,external_api_calls=0));print(dict(papers=101,changed_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows)))


if __name__=='__main__':main()
