"""Split the stored continuous method into stages without changing property results."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha
from propose_saved_solution_casting_chain import DEST

TRIAL=OUT/'process_relation_trial_036'
EXTENSION='process_saved_solution_casting_chain'


def build(p,reviewmeta):
    g=dict(operations=[],states=[],bindings=[],orders=[],parameters=[],material_identity_nodes=[],saved_quote=deepcopy(p['saved_quote']),
        captures=deepcopy(p['captures']),lineages=deepcopy(p['lineages']),source_approval=reviewmeta,shared_method_template_not_a_pool_of_eleven_polymers=True,
        solvent_choice_per_lineage_not_reported=True,neat_DMAc_solubility_of5f_not_silently_resolved=True,new_primary_source_values=0,external_api_calls=0)
    labels=[x['label'] for x in g['lineages']]
    g['material_identity_nodes'].append(dict(id='POLYMER_BATCH_IDENTITIES',kind='material_identity',labels=labels,identity_only_not_an_initial_solid_phase_assertion=True))
    def par(key,role,unit=None):
        c=g['captures'][key];d=dict(role=role,value_raw=c['value_raw'],source_capture=key)
        if unit:d['unit_normalized']=unit
        return d
    specs=[
        ('DISSOLVE','dissolve polymer in the reported hot solvent alternative',
            [par('polymer_mass','approximate polymer amount','g'),par('solvent_volume','solvent volume','mL'),par('dissolution_medium','alternative hot solvent; not a mixture'),par('solution_concentration','source-reported approximate solution concentration','wt %')],
            'clear approximately10wt% polymer solution in the reported hotDMAc-orNMP alternative'),
        ('POUR','pour the clear solution into the glass culture dish',[par('dish_diameter','glass culture-dish diameter','cm')],
            'cast clear polymer solution in the source glass culture dish'),
        ('EVAPORATE','evaporate solvent in the oven',[par('evaporation_temperature','oven temperature','°C'),par('evaporation_duration','overnight qualitative duration')],
            'semidried polyamide film on the glass surface after oven solvent removal'),
        ('STRIP','strip the semidried polyamide film from the glass',[],
            'freestanding semidried polyamide film stripped from the glass'),
        ('VACUUM_DRY','further dry the freestanding film in vacuum',[par('drying_pressure','qualitative drying pressure'),par('drying_temperature','drying temperature','°C'),par('drying_duration','drying duration','h')],
            'vacuum-dried source polyamide film')]
    previous=None
    for step,name,pars,desc in specs:
        oid='CASTING_'+step;sid=oid+'_STATE';op=dict(id=oid,kind='operation',name=name,scope='named_native_film_branches',applicable_sample_labels=labels,
            parameters=pars,output_state_id=sid,source_quote_sha256=p['saved_quote']['text_sha256'])
        if previous:op['input_state_id']=previous+'_STATE'
        else:op['input_material_id']='POLYMER_BATCH_IDENTITIES'
        g['operations'].append(op);g['states'].append(dict(id=sid,kind='state',identity=labels,stage='after '+name,state=desc,
            operation_id=oid,each_lineage_a_separate_method_application=True))
        g['bindings'].append(dict(id='B_'+oid,kind='binding',operation_id=oid,output_state_id=sid,lineage_labels=labels,
            relation='this_intermediate_or_final_stage_applies_to_each_source_named_film_branch_independently'))
        if previous:g['orders'].append(dict(id='O_'+previous+'_'+oid,kind='order',before_operation_id=previous,after_operation_id=oid,
            scope='same_film_method_and_same_lineage_only',source_quote_sha256=p['saved_quote']['text_sha256']))
        previous=oid
    g['operations'][0]['no_density_based_concentration_recalculation']=True
    g['operations'][2]['vacuum_not_reported_for_this_stage']=True
    g['operations'][-1]['vacuum_pressure_numeric_not_reported']=True
    g['states'][-1]['final_film_thickness_raw']=p['native_film_thickness']['value_raw'];g['states'][-1]['geometry_source_pointer']=p['native_film_thickness']['pointer']
    g['states'][-1]['thickness_approximately_reported']=True
    g['bindings'].append(dict(id='B_COMPLETE_BATCH_TO_FILM_LINEAGES',kind='binding',lineages=deepcopy(p['lineages']),
        operation_ids=[x['id'] for x in g['operations']],final_state_id=g['states'][-1]['id'],original_native_step_pointer=p['native_casting_step_pointer'],
        relation='source_named_synthesis_identity_to_matching_named_processed_film_through_reported_shared_method',
        no_measurement_specimen_or_solubility_aliquot_merged=True))
    g['scope_notes']=['HotDMAc-orNMP remains an unresolved alternative for each lineage.','Source5f neatDMAc disagreement is not repaired by assumingNMP or heatedDMAc.',
        'The source batch-to-film identity is not a claim that DSC,viscosity andsolubility tests reused this same physical film.',
        'No polymerization recipe, extra NMP addition, film quality, chemistry, IR preparation or thermal-analysis stage is added from reference diagnosis.']
    return g


def main():
    pp=OUT/'process_relation_trial_035/freeze.json';parent=read(pp);packet=read(DEST/'proposal.json');p,=packet['proposals'];rp=DEST/'source_approval.json';approval=read(rp)
    assert packet['parent_trial_freeze_sha256']==sha(pp) and approval['proposal_sha256']==sha(DEST/'proposal.json')
    assert not (TRIAL/'freeze.json').exists();rows=[]
    for old in parent['papers']:
        assert sha(old['candidate_path'])==old['candidate_sha256'];r=deepcopy(old);r['changed_from_immediate_parent']=False
        if old['reference_no']==p['reference_no']:
            pred=read(old['candidate_path']);assert EXTENSION not in pred;pred[EXTENSION]=[build(p,dict(path=str(rp),sha256=sha(rp)))];cp=TRIAL/'papers'/(old['reference_no']+'.json');save(cp,pred)
            r.update(candidate_path=str(cp),candidate_sha256=sha(cp),changed_from_parent=True,changed_from_immediate_parent=True,
                immediate_parent_candidate_path=old['candidate_path'],immediate_parent_candidate_sha256=old['candidate_sha256'])
        rows.append(r)
    save(TRIAL/'freeze.json',dict(version=TRIAL.name,parent_trial='process_relation_trial_035',parent_trial_freeze_sha256=sha(pp),baseline_candidate='candidate_v10',
        baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),
        proposal_generation_code_sha256=sha(OUT/'propose_saved_solution_casting_chain.py'),papers=rows,papers_total=101,changed_papers_this_round=1,
        cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows),property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,
        reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,whole_batch_reextraction=False,stable_workflow_release=False,external_api_calls=0))
    print(dict(changed_this_round=1,old_method_stages=5,lineages=len(p['lineages']),new_source_values=0,scored=False))


if __name__=='__main__':main()
