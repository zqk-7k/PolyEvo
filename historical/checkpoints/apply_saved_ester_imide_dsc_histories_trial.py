"""Append source-checked saved thermal histories; no reference or new PDF values."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha
from propose_saved_ester_imide_dsc_histories import DEST

TRIAL=OUT/'process_relation_trial_031'
EXTENSION='process_saved_ester_imide_dsc_histories_recovery'


def build(packet,reviewmeta):
    g=dict(operations=[],parameters=[],states=[],bindings=[],orders=[],measurement_annotations=[],step_index=[],
           saved_fragments=deepcopy(packet['saved_fragments']),sample_anchors=deepcopy(packet['sample_anchors']),
           source_approval=reviewmeta,original_property_values_and_bindings_unchanged=True,new_pdf_information_extracted=0,external_api_calls=0)
    groups=packet['groups'];v=lambda f,k:packet['saved_fragments'][f]['captures'][k]['value_raw']
    def par(role,f,key,unit=None):
        p=dict(role=role,value_raw=v(f,key),source_fragment=f,source_capture=key)
        if unit:p['unit_normalized']=unit
        return p
    def add(ident,name,group,frag,params,state,**flags):
        targets=groups[group];ptrs=[packet['sample_anchors'][label]['pointer'] for label in targets];sid=ident+'_STATE'
        g['operations'].append(dict(id=ident,kind='operation',name=name,scope=targets,original_sample_pointers=ptrs,
            output_state_id=sid,parameters=params,source_fragment=frag,shared_scope_not_physical_pooling=True,**flags))
        g['states'].append(dict(id=sid,kind='state',identity=targets,original_sample_pointers=ptrs,stage='during/after '+name,state=state,
            operation_id=ident,source_fragment=frag,unreported_physical_phase_not_inferred=True))
        g['bindings'].append(dict(id='B_'+ident,kind='binding',operation_id=ident,output_state_id=sid,original_sample_pointers=ptrs,
            applicable_sample_labels=targets,relation='reported_operation_and_state_for_each_source_named_specimen',source_fragment=frag,physical_specimens_not_pooled=True))
        g['step_index'].append(dict(id=ident,operation_index=len(g['operations'])-1,state_index=len(g['states'])-1,binding_index=len(g['bindings'])-1))
    rate=lambda:par('actual DSC specimen heating rate','five','scan_rate','°C/min')
    add('FIVE_FIRST','first DSC specimen heating','five_first_second','five',[rate()],'5c/5d/5e during first heating histories',rate_is_not_synthesis_or_cooling_rate=True)
    add('FIVE_SECOND','second DSC specimen heating','five_first_second','five',[rate()],'previously heated5c/5d/5e during second heating histories',rate_is_not_synthesis_or_cooling_rate=True,intervening_cooling_program_not_reported=True)
    add('FIVE_D_COOL','reported DSC specimen cooling','cooling','five',[],'5d during the reported cooling history',cooling_rate_not_reported=True)
    add('FIVE_AD_ANNEAL','annealing the source-named five-series specimens','five_annealed','five',[par('annealing temperature','five','anneal_temperature','°C')],
        '65°C-annealed5a/5b/5c/5d specimens; no unreported morphology assigned',duration_not_reported=True,condition_not_extended_to5e=True)
    add('FIVE_BETWEEN','annealing between the two endotherms','five_first_second','five',[par('qualitative annealing temperature range','five','between_endotherms')],
        '5c/5d/5e after source-reported between-endotherm annealing',numeric_temperature_and_duration_not_reported=True,alternative_not_consecutive_to_second_heating=True)
    add('SEVEN_B_DRY','drying7b before DSC','seven_dried','seven',[par('drying temperature','seven','dry_temperature','°C')],'110°C-dried7b specimen',drying_duration_pressure_not_reported=True)
    add('SEVEN_B_HEAT','heating dried7b for the reported DSC endotherm','seven_dried','seven',[],'7b thermally examined; original optical microscopy confirms an isotropic melt',heating_rate_stop_temperature_not_reported=True,optical_and_DSC_observations_not_claimed_same_physical_replica=True)
    add('SEVEN_A_FIRST','first DSC heating of7a','seven_other','seven',[],'7a during first heating history',heating_rate_and_stop_temperature_not_reported=True)
    add('SEVEN_A_SECOND','second DSC heating of7a','seven_other','seven',[],'previously heated7a during second heating history',heating_rate_and_intervening_program_not_reported=True)
    add('SEVEN_A_ANNEAL','brief annealing of7a','seven_other','seven',[par('annealing temperature','seven','anneal_temperature','°C'),par('duration description','seven','short_duration_description')],
        '7a after source-reported brief110°C annealing',numeric_duration_not_reported=True,not7b_drying=True)
    add('SIX_AH_ANNEAL','annealing the source-named six-series specimens','six_annealed','six',[par('annealing temperature','six','anneal_temperature','°C')],
        '110°C-annealed6a–6h; no universal amorphous or single6d thermal-branch state assigned',duration_not_reported=True,not_specific6d_figure7_branches=True)
    for a,b,group,frag in [('FIVE_FIRST','FIVE_SECOND','five_first_second','five'),('SEVEN_B_DRY','SEVEN_B_HEAT','seven_dried','seven'),('SEVEN_A_FIRST','SEVEN_A_SECOND','seven_other','seven')]:
        g['orders'].append(dict(id='O_'+a+'_'+b,kind='order',before_operation_id=a,after_operation_id=b,scope=groups[group],source_fragment=frag,
            relation='precedes_in_the_reported_preconditioning_or_relative_heating_history',consecutive_operations_not_asserted=True,physical_replica_identity_not_established=True))
    targets=groups['seven_other'];ptrs=[packet['sample_anchors'][x]['pointer'] for x in targets]
    g['states'].append(dict(id='SEVEN_A_ISOTROPIC_MELT',kind='state',identity=targets,original_sample_pointers=ptrs,stage='optically observed molten state, timing relative to DSC traces unspecified',
        state='isotropic melt',source_fragment='seven',not_assigned_to_a_specific_DSC_trace=True))
    g['bindings'].append(dict(id='B_SEVEN_A_ISOTROPIC_MELT',kind='binding',state_id='SEVEN_A_ISOTROPIC_MELT',original_sample_pointers=ptrs,
        applicable_sample_labels=targets,relation='source_explicit_optical_melt_observation_for7a',source_fragment='seven',no_specific_DSC_replica_inferred=True))
    for ident,labels,summary,frag in [
        ('FIVE_FIRST_RESPONSE',groups['five_first_second'],'two neighbouring first-heating endotherms','five'),
        ('FIVE_SECOND_RESPONSE',groups['five_first_second'],'one endotherm in second heating or after separate between-endotherm annealing','five'),
        ('FIVE_D_RESPONSE',groups['cooling'],'no Tg detected in the reported cooling or second heating curve; weak first-heating feature not used as an annealing setpoint','five'),
        ('FIVE_AD_RESPONSE',groups['five_annealed'],'no Tg detected after the source65°C annealing condition','five'),
        ('SEVEN_B_RESPONSE',groups['seven_dried'],'one sharp endotherm, no other reported phase transition','seven'),
        ('SEVEN_A_RESPONSE',groups['seven_other'],'two endotherms in first and second heating, coalescing into one after brief110°C annealing','seven'),
        ('SIX_AH_RESPONSE',groups['six_annealed'],'source reports comparatively lower crystallinity despite110°C annealing, not complete amorphization','six')]:
        g['measurement_annotations'].append(dict(id=ident,annotation_type='measurement_response_not_additional_process_state_or_parameter',sample_labels=labels,description=summary,source_fragment=frag))
    return g


def main():
    proposal=DEST/'proposal.json';packet=read(proposal);review=DEST/'source_approval.json';approval=read(review)
    assert approval['proposal_sha256']==sha(proposal) and sha(packet['parent_prediction_path'])==packet['parent_prediction_sha256']
    pp=OUT/'process_relation_trial_030/freeze.json';parent=read(pp);assert packet['parent_trial_freeze_sha256']==sha(pp)
    assert not (TRIAL/'freeze.json').exists();rows=[]
    for p in parent['papers']:
        assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
        if p['reference_no']==packet['reference_no']:
            pred=read(p['candidate_path']);assert EXTENSION not in pred;pred[EXTENSION]=[build(packet,dict(path=str(review),sha256=sha(review)))];dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,pred)
            row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,
                immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
        rows.append(row)
    save(TRIAL/'freeze.json',dict(version=TRIAL.name,parent_trial='process_relation_trial_030',parent_trial_freeze_sha256=sha(pp),
        baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),
        proposal_generation_code_sha256=sha(OUT/'propose_saved_ester_imide_dsc_histories.py'),papers=rows,papers_total=101,changed_papers_this_round=1,
        cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows),property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,
        reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,whole_batch_reextraction=False,stable_workflow_release=False,external_api_calls=0))
    print(dict(papers=101,changed_this_round=1,old_quotes=3,new_source_pages=0,scored=False))


if __name__=='__main__':main()
