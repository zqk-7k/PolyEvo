"""Add source-note scope to existing actual schedules, with originals intact."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha,canonical
from extract_polyester_targeted_footnotes import DEST

TRIAL=OUT/'process_relation_trial_028'
EXTENSION='process_polyester_targeted_table2_notes_supplement'
OLD_EXTENSION='process_saved_polyester_schedule_recovery'


def build(old,source,source_meta):
    g=dict(operations=[],parameters=[],states=[],bindings=[],orders=[],schedule_index=[],measurement_index=[],
           source_notes=deepcopy(source),source_prediction_freeze=source_meta,
           new_source_papers=1,new_source_pages=1,old_actual_conditions_not_reextracted=True,
           original_property_values_and_bindings_unchanged=True,external_api_calls=0)
    oldroot='/'+OLD_EXTENSION+'/0/'
    for row in old['parsed_saved_table_rows']:
        label=row['label'];anchor=row['existing_sample_anchor']; entries=[x for x in old['condition_index'] if x['label']==label]
        assert len(entries)==len(row['condition_pairs']) and [x['reported_entry_index'] for x in entries]==list(range(len(entries)))
        pointers=[oldroot+'operations/'+str(x['operation_pointer_index']) for x in entries]
        for a,b in zip(pointers,pointers[1:]):
            g['orders'].append(dict(id='STEPWISE_'+label+'_'+str(len(g['orders'])),kind='order',before_operation_pointer=a,after_operation_pointer=b,
                                    scope=label,relation='precedes_within_same_reported_stepwise_polycondensation',
                                    source_footnote='table2_note_a',no_intervening_conditions_inferred=True))
        vacuum=[]
        for entry,ptr in zip(entries,pointers):
            o=old['operations'][entry['operation_pointer_index']]
            if o.get('uninterpreted_source_tag')==source['thermal_schedule_description']['tag']:
                vacuum.append(ptr);g['parameters'].append(dict(id='VACUUM_'+o['id'],kind='parameter',role='reaction atmosphere or pressure regime',
                    value_raw=source['thermal_schedule_description']['tag_meaning'],operation_pointer=ptr,scope=label,source_footnote='table2_note_a',
                    source_tag=entry['tag'],numerical_pressure_not_reported=True,untagged_steps_not_assumed_in_air=True))
        sid='POLYCONDENSATION_ENDPOINT_'+label
        g['states'].append(dict(id=sid,kind='state',identity=label,original_sample_pointer=anchor['pointer'],
                               stage='after the reported stepwise thermal polycondensation ending in its V-tagged stage',
                               state='polyester after its reported thermal preparation history; final step under vacuum',
                               ordered_operation_pointers=pointers,vacuum_operation_pointers=vacuum,
                               physical_phase_cooling_and_drying_not_inferred=True,source_footnote='table2_note_a'))
        g['bindings'].append(dict(id='B_SCHEDULE_'+label,kind='binding',scope=label,original_sample_pointer=anchor['pointer'],
                                 ordered_operation_pointers=pointers,vacuum_operation_pointers=vacuum,output_state_id=sid,
                                 relation='one_reported_table_row_is_one_stepwise_preparation_history',
                                 source_footnote='table2_note_a',not_independent_temperature_combinations=True))
        g['schedule_index'].append(dict(label=label,entry_operation_pointers=pointers,endpoint_state_index=len(g['states'])-1,
                                       binding_index=len(g['bindings'])-1,vacuum_operation_pointers=vacuum))
        # Only actual numeric viscosity rows acquire a measured-solution context.
        indicator=row['viscosity_indicator']['value_raw']
        if label not in old['eligible_workup_labels']:
            assert 'Insol' in indicator;continue
        context=source['viscosity_measurement_context'];sid='VISCOSITY_SOLUTION_'+label
        g['states'].append(dict(id=sid,kind='state',identity=label,original_sample_pointer=anchor['pointer'],stage='during the reported inherent-viscosity measurement',
                               state='measured polyester solution in the source-specified mixed solvent',measurement_context=deepcopy(context),
                               source_footnote='table2_note_b',not_a_dissolution_operation=True,not_a_reaction_medium=True))
        for role,value,unit in [('measurement solution concentration',context['concentration_value'],context['concentration_unit']),
                                ('measurement temperature',context['temperature_value'],context['temperature_unit']),
                                ('measurement solvent volume ratio',context['solvent_volume_ratio'],'volume ratio')]:
            g['parameters'].append(dict(id='VISCOSITY_'+label+'_'+str(len(g['parameters'])),kind='parameter',role=role,value_raw=value,unit_normalized=unit,
                                        ordered_medium_names=context['ordered_medium_names'],state_id=sid,scope=label,source_footnote='table2_note_b',
                                        applies_to_measurement_not_polymerization=True))
        g['bindings'].append(dict(id='B_VISCOSITY_'+label,kind='binding',scope=label,original_sample_pointer=anchor['pointer'],output_state_id=sid,
                                 relation='actual_numeric_viscosity_row_has_the_reported_measured_solution_context',
                                 old_numeric_cell_provenance=deepcopy(row['viscosity_indicator']),new_property_value_not_generated=True,source_footnote='table2_note_b'))
        g['measurement_index'].append(dict(label=label,state_index=len(g['states'])-1,binding_index=len(g['bindings'])-1))
    g['scope_notes']=['The earlier old-cache graph recorded the footnote meaning and temporal order as unknown. This additive source supplement resolves those unknowns without rewriting its archived fields.',
                      'V is interpreted only where that exact tag exists. No absolute pressure, heating rate, cooling step or atmosphere of untagged stages is inferred.',
                      'The measured-solution note applies to numeric reported viscosity rows only. Insoluble2c is not given a successful solution or zero viscosity.']
    return g


def main():
    parentpath=OUT/'process_relation_trial_027/freeze.json';parent=read(parentpath)
    sf=DEST/'prediction_freeze.json';sourcef=read(sf);assert sha(sourcef['graph_path'])==sourcef['graph_sha256'];source=read(sourcef['graph_path'])
    assert not (TRIAL/'freeze.json').exists();rows=[]
    for p in parent['papers']:
        assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
        if p['reference_no']=='reference_no_0011437':
            pred=read(p['candidate_path']);assert EXTENSION not in pred
            pred[EXTENSION]=[build(pred[OLD_EXTENSION][0],source,dict(path=str(sf),sha256=sha(sf)))];dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,pred)
            row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,
                       immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
        rows.append(row)
    save(TRIAL/'freeze.json',dict(version=TRIAL.name,parent_trial='process_relation_trial_027',parent_trial_freeze_sha256=sha(parentpath),
                                 baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),
                                 prediction_application_code_sha256=sha(__file__),source_prediction_freeze=dict(path=str(sf),sha256=sha(sf)),papers=rows,papers_total=101,
                                 changed_papers_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows),
                                 property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,
                                 reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=1,
                                 new_pdf_information_unit='one original PDF page, two Table2 footnote blocks only',old_actual_table_rows_reused=9,
                                 whole_batch_reextraction=False,stable_workflow_release=False,external_api_calls=0))
    print(dict(papers=101,changed_this_round=1,source_notes=2,new_source_pages=1,property_modified=False,scored=False))


if __name__=='__main__':main()
