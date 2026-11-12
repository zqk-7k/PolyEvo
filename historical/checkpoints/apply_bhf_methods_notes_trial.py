"""Combine frozen old actual rows with frozen primary-source method/note scopes."""
import re
from copy import deepcopy
from prepare_audit import OUT,read,save,sha,canonical

TRIAL=OUT/'process_relation_trial_027'
EXTENSION='process_bhf_targeted_methods_notes_supplement'


def build(methods,packet,source_meta):
 g=deepcopy(methods);p=packet['proposals'][0];bykey={(r['route'],r['step']):g['operations'][r['operation_index']]['id'] for r in g['method_step_index']};g['row_condition_index']=[];g['saved_old_tables']=deepcopy(p['tables']);g['saved_old_fragments']=deepcopy(p['fragments']);g['saved_old_table_proposal_source']=source_meta;g['observed_composition_annotations']=[]
 for table in p['tables']:
  key=table['table'];defaultkey={'T1':'table1','T2':'table2','T3':'table3'}[key];defaults=g['table_defaults'][defaultkey];route='acid_chloride_method' if key=='T1' else 'DCC_method';methodids=[o['id'] for o in g['operations'] if o['scope']==route];prep=bykey[(route,'PREPARE' if key=='T1' else 'PREACTIVATE')];main=bykey[(route,'MAIN_REACTION' if key=='T1' else 'ADD_BHF_AND_REACT')]
  for row in table['rows']:
   local=row['local_product_key'];oid='ROW_CONDITION_'+local;pars=deepcopy(defaults['parameters']);marker=row['row_label'][len(row['numeric_row_label']):];exception=next((x for x in defaults['exceptions'] if x['run_marker']==marker),None)
   if exception:pars=[x for x in pars if x['role']!=exception['overrides_role']]+[deepcopy(exception['replacement_parameter'])]
   for par in pars:par['source_origin']='new_primary_source_table_note'
   inputs=[dict(code='BHF',identity_source='experimental monomer preparation and table common note')]
   if key in ['T1','T2']:
    solvent=row['solvent'];code=solvent['code'];name=g['chemical_legend'].get(code,{}).get('value_raw',code)
    pars += [dict(role='reaction solvent',value_raw=code,source_normalized_name=name,old_source_cell=solvent['source_cell'],source_old_table=key,source_origin='old_table_row_condition_with_source_verified_code'),dict(role='reaction solvent volume',value_raw=solvent['volume_raw'],unit_normalized='mL',medium_code=code,old_source_cell=solvent['source_cell'],source_old_table=key,source_origin='old_table_row_condition')]
   if key=='T1':inputs.append(dict(name_raw='succinyl chloride',identity_source='acid-chloride method and Table1 common note'))
   elif key=='T2':
    acid=row['acid_code'];name=g['chemical_legend'][acid]['value_raw'];inputs.append(dict(code=acid,source_normalized_name=name));pars.append(dict(role='carboxylic acid charge mass',value_raw=row['acid_mass_raw'],unit_normalized='mg',substance_code=acid,substance_name=name,old_source_cell=row['cells'][1],source_old_table=key,source_origin='old_table_row_condition'))
   else:
    inputs.extend(dict(code=c,source_normalized_name=g['chemical_legend'][c]['value_raw']) for c in [row['first_acid_code'],row['second_acid_code']]);pars.append(dict(role='acid feed molar ratio',value_raw=row['feed_ratio_raw'],unit_normalized='molar ratio',ordered_components=[row['first_acid_code'],row['second_acid_code']],old_source_cell=row['cells'][1],source_old_table=key,source_origin='old_table_row_condition',not_measured_copolymer_composition=True))
   for par in pars:
    role=par['role']
    if key=='T1':stage=bykey[(route,'ADD_AND_REACT')] if role.startswith('succinyl chloride') else main if role.startswith(('reaction temperature','reaction duration')) else prep
    else:stage=main if role.startswith(('BHF','reaction temperature','reaction duration')) else prep
    par['applicable_method_operation_id']=stage
   mid=local+'_PRODUCT';g['material_identity_nodes'].append(dict(id=mid,kind='material_identity',identity=local,source_table=key,source_run_label=row['row_label'],input_materials=deepcopy(inputs),physical_phase_not_inferred=True))
   g['operations'].append(dict(id=oid,kind='operation',name='reported row-specific polycondensation preparation',scope=local,record_role='method_condition_instance_not_an_extra_reaction_execution',input_materials=inputs,output_material_id=mid,parameters=pars,reported_method_operation_ids=methodids,source_table=key,old_saved_row_label=row['row_label'],table_default_scope=defaultkey,temperature_exception_marker=marker or None,default_main_temperature_overridden=bool(exception),row_solvent_overrides_nominal_method_solvent=key in ['T1','T2'],BHF_not_assumed_charged_with_DCC_before_preactivation=key!='T1',source_conditions_not_transferred_between_tables=True))
   g['bindings'].append(dict(id='B_'+oid,kind='binding',operation_id=oid,output_material_id=mid,method_operation_ids=methodids,relation='this_actual_saved_row_instantiates_the_reported_method_with_scoped_conditions',source_table=key,source_run_label=row['row_label'],BHF_chemical_identity_source_state_id=g['operations'][g['method_step_index'][13]['operation_index']]['output_state_id'],same_single_BHF_batch_for_all_rows_not_asserted=True,shared_method_variables_not_physical_pooling=True,per_parameter_stage_assignment_explicit=True))
   record=dict(table=key,row_label=row['numeric_row_label'],operation_index=len(g['operations'])-1,binding_index=len(g['bindings'])-1,material_id=mid);g['row_condition_index'].append(record)
   if key=='T3':
    composition=dict(material_id=mid,kind='molecular_composition_annotation',ordered_components=[row['first_acid_code'],row['second_acid_code']],value_raw=row['product_composition_cell']['value_raw'],unit_description='reported acid-unit composition ratio',source_old_table=key,old_source_cell=row['product_composition_cell'],measurement_method=deepcopy(g['copolymer_composition_method']),not_an_input_feed_and_not_a_new_property_value=True)
    g['observed_composition_annotations'].append(composition);g['bindings'].append(dict(id='B_FEED_TO_COMPOSITION_'+local,kind='binding',operation_id=oid,output_material_id=mid,relation='reported_feed_and_distinct_observed_unit_composition_for_this_copolyester',feed_ratio_raw=row['feed_ratio_raw'],observed_composition_annotation_index=len(g['observed_composition_annotations'])-1,source_table=key,same_row_and_same_component_order=True))
 # Explicitly declare the operational boundary; old cited-biomass context is
 # provenance, never a processing step or a numeric experimental parameter.
 cache=read(packet['cache_path']);q=max((q for q in cache['source_quotations'] if '望月らは' in q['text'] and '260' in q['text']),key=lambda q:len(q['text']));g['experimental_scope_annotation']=dict(current_source_workflow_starts_with='HMF reduction to BHF, then polyester preparations',cited_biomass_treatment_is_not_an_extracted_current_experiment=True,old_cited_context=dict(existing_quote=q,text_sha256=canonical(q['text'])),new_experimental_source_fragment='experimental_2_2')
 g['bindings'].append(dict(id='B_EXPERIMENTAL_START_SCOPE',kind='binding',relation='current_HMF_to_BHF_experiment_distinguished_from_cited_biomass_background',source_fragment='experimental_2_2',old_cited_context_pointer='experimental_scope_annotation/old_cited_context',literature_treatment_not_used_as_polymerization_condition=True))
 return g


def main():
 parentpath=OUT/'process_relation_trial_026/freeze.json';parent=read(parentpath);sf=OUT/'targeted_source_supplements/reference_no_0030402_methods_notes/reviewed_prediction_freeze.json';source=read(sf);assert sha(source['graph_path'])==source['graph_sha256'];methods=read(source['graph_path']);oldpath=OUT/'saved_bhf_condition_tables_recovery/papers/reference_no_0030402.json';packet=read(oldpath);assert sha(packet['cache_path'])==packet['cache_sha256'];rows=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no']=='reference_no_0030402':
   new=read(p['candidate_path']);assert EXTENSION not in new;new[EXTENSION]=[dict(graph=build(methods,packet,dict(path=str(oldpath),sha256=sha(oldpath))),source_prediction_freeze_path=str(sf),source_prediction_freeze_sha256=sha(sf),source_review_path=source['source_review_path'],source_review_sha256=source['source_review_sha256'],source_methods_and_saved_rows_combined_only_after_separate_freezes=True,original_property_values_and_bindings_unchanged=True)];dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new);row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  rows.append(row)
 save(TRIAL/'freeze.json',dict(version=TRIAL.name,parent_trial='process_relation_trial_026',parent_trial_freeze_sha256=sha(parentpath),baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),source_supplement_prediction_freeze=dict(path=str(sf),sha256=sha(sf)),papers=rows,papers_total=101,changed_papers_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows),property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=2,new_pdf_information_unit='two original PDF pages, experimental and table-note regions only',source_table_bodies_not_reextracted=True,old_actual_table_rows_reused=25,whole_batch_reextraction=False,stable_workflow_release=False,external_api_calls=0));print(dict(papers=101,changed_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows),new_source_pages=2,old_actual_rows_reused=25,whole_batch_reextraction=False))


if __name__=='__main__':main()
