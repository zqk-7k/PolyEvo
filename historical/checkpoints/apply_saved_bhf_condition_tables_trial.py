"""Apply old row conditions without inventing shared footnote quantities."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha

TRIAL=OUT/'process_relation_trial_025'
EXTENSION='process_saved_bhf_condition_tables_recovery'


def build(p,approval):
 ops=[];bindings=[];nodes=[];index=[]
 for table in p['tables']:
  key=table['table'];context={'T1':'acid_chloride_context','T2':'DCC_context','T3':'copolyester_context'}[key];caps=p['fragments'][context]['captures']
  for r in table['rows']:
   ident=r['local_product_key'];oid='PREPARE_'+ident;params=[]
   if key in ['T1','T2']:
    s=r['solvent'];params.extend([dict(role='reaction solvent code',value_raw=s['code'],raw_source_code_and_marker=s['raw_code_and_marker'],source_cell=s['source_cell']),dict(role='reaction solvent volume',value_raw=s['volume_raw'],unit_normalized='mL',medium_code=s['code'],source_cell=s['source_cell'])])
   if key=='T1':inputs=[caps['diol']['value_raw'],caps['acid_chloride']['value_raw']]
   elif key=='T2':
    inputs=[caps['diol']['value_raw'],r['acid_code']];params.extend([dict(role='carboxylic acid charge mass',value_raw=r['acid_mass_raw'],unit_normalized='mg',substance_code=r['acid_code'],source_cell=r['cells'][1]),dict(role='coupling agent code',value_raw=caps['coupling_code']['value_raw'],source_context_fragment=context,source_capture='coupling_code',coupling_agent_amount_unknown=True)])
   else:
    inputs=[caps['diol']['value_raw'],r['first_acid_code'],r['second_acid_code']];params.append(dict(role='acid feed molar ratio',value_raw=r['feed_ratio_raw'],unit_normalized='molar ratio',ordered_components=[r['first_acid_code'],r['second_acid_code']],source_cell=r['cells'][1],not_measured_copolymer_composition=True))
   nodes.append(dict(id=ident,kind='material_identity',table_namespace=key,source_run_label=r['row_label'],identity='BHF polyester preparation '+key+' run '+r['row_label'],reaction_inputs_raw=inputs,source_table=key,physical_phase_not_inferred=True))
   ops.append(dict(id=oid,kind='operation',name='reported BHF polycondensation condition' if key!='T3' else 'reported BHF copolycondensation feed condition',scope=ident,input_materials_raw=inputs,output_material_id=ident,parameters=params,source_table=key,source_context_fragment=context,shared_charge_temperature_time_and_workup_not_recovered=True,uninterpreted_run_marker=r['row_label'][len(r['numeric_row_label']):] or None))
   bindings.append(dict(id='B_'+ident,kind='binding',operation_id=oid,output_material_id=ident,table_namespace=key,source_run_label=r['row_label'],relation='actual_saved_table_row_preparation_identity',source_table=key,distinct_table_numbers_not_merged=True));index.append(dict(table=key,row_label=r['numeric_row_label'],operation_index=len(ops)-1,material_index=len(nodes)-1,binding_index=len(bindings)-1))
 return dict(operations=ops,parameters=[],states=[],orders=[],bindings=bindings,material_identity_nodes=nodes,material_identity_nodes_not_material_states=True,condition_index=index,saved_fragments=deepcopy(p['fragments']),parsed_saved_tables=deepcopy(p['tables']),shared_footnote_values_not_recovered=True,source_approval_path=approval['path'],source_approval_sha256=approval['sha256'],original_property_values_and_bindings_unchanged=True,new_pdf_information_extracted=0)


def main():
 parentpath=OUT/'process_relation_trial_024/freeze.json';parent=read(parentpath);approval,=read(OUT/'saved_bhf_condition_tables_recovery/source_reviews/manifest.json')['papers'];assert sha(approval['path'])==approval['sha256'];review=read(approval['path']);assert sha(review['proposal_path'])==review['proposal_sha256'];packet=read(review['proposal_path']);rows=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no']==approval['reference_no']:
   new=read(p['candidate_path']);assert EXTENSION not in new;new[EXTENSION]=[build(packet['proposals'][0],approval)];dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new);row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  rows.append(row)
 save(TRIAL/'freeze.json',dict(version=TRIAL.name,parent_trial='process_relation_trial_024',parent_trial_freeze_sha256=sha(parentpath),baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),proposal_generation_code_sha256=sha(OUT/'propose_saved_bhf_condition_tables.py'),papers=rows,papers_total=101,changed_papers_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows),property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,stable_workflow_release=False,external_api_calls=0));print(dict(papers=101,changed_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows)))


if __name__=='__main__':main()
