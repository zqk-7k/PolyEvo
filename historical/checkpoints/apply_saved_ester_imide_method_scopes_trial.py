"""Repair old method scopes and sample conditions, without new source values."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha
from propose_saved_ester_imide_method_scopes import DEST

TRIAL=OUT/'process_relation_trial_032'
EXTENSION='process_saved_ester_imide_method_scopes_recovery'


def build(packet,approval,reviewmeta):
    g=dict(operations=[],parameters=[],states=[],bindings=[],orders=[],material_identity_nodes=[],step_index=[],
           saved_fragments=deepcopy(packet['saved_fragments']),sample_anchors=deepcopy(packet['sample_anchors']),
           source_approval=reviewmeta,original_property_values_and_bindings_unchanged=True,new_pdf_information_extracted=0,external_api_calls=0)
    v=lambda f,k:packet['saved_fragments'][f]['captures'][k]['value_raw']
    def par(role,f,key,unit=None):
        x=dict(role=role,value_raw=v(f,key),source_fragment=f,source_capture=key)
        if unit:x['unit_normalized']=unit
        return x
    def identity(ident,name):g['material_identity_nodes'].append(dict(id=ident,kind='material_identity',identity=name,physical_phase_unknown=True,method_variable_not_actual_pooled_batch=True))
    identity('DIPHENOL_INPUT','acetylated-diphenol polycondensation reaction vessel')
    identity('ALKANEDIOL_INPUT','alkanediol polycondensation reaction vessel')
    def add_context(ident,name,scope,fragment,pars,inputid):
        out=ident+'_MATERIAL';identity(out,name+' context')
        g['operations'].append(dict(id=ident,kind='operation',name=name,scope=scope,input_material_id=inputid,output_material_id=out,
            parameters=pars,source_fragment=fragment,no_missing_charge_or_physical_phase_inferred=True))
        g['bindings'].append(dict(id='B_'+ident,kind='binding',operation_id=ident,input_material_id=inputid,output_material_id=out,
            relation='reported_step_in_this_source_named_method',source_fragment=fragment,not_a_specific_final_product_reheating=True))
        g['step_index'].append(dict(id=ident,operation_index=len(g['operations'])-1,binding_indices=[len(g['bindings'])-1]));return out
    bath=approval['bath_source_role_map']
    a=add_context('DIPHENOL_BATH','place reaction vessel in preheated metal bath','acetylated_diphenol_method','diphenol_heading',[par('bath preheat temperature',bath['diphenol'],'temperature','°C')],'DIPHENOL_INPUT')
    b=add_context('DIPHENOL_START','rapidly raise temperature to initiate polycondensation','acetylated_diphenol_method','diphenol_initiation',[par('initiation temperature','diphenol_initiation','temperature','°C')],a)
    add_context('DIPHENOL_RAISE','raise reaction temperature in reported steps','acetylated_diphenol_method','diphenol_schedule',
        [par('endpoint temperature','diphenol_schedule','target','°C'),par('temperature increment','diphenol_schedule','increment','°C'),par('total stepwise temperature-raising duration','diphenol_schedule','duration','h')],b)
    c=add_context('ALKANEDIOL_BATH','place reaction vessel in preheated metal bath','alkanediol_method','alkanediol_heading',[par('bath preheat temperature',bath['alkanediol'],'temperature','°C')],'ALKANEDIOL_INPUT')
    add_context('ALKANEDIOL_RAISE','raise reaction temperature in reported steps','alkanediol_method','alkanediol_schedule',
        [par('endpoint temperature','alkanediol_schedule','target','°C'),par('temperature increment','alkanediol_schedule','increment','°C'),par('total stepwise temperature-raising duration','alkanediol_schedule','duration','h')],c)
    for left,right in [('DIPHENOL_BATH','DIPHENOL_START'),('DIPHENOL_START','DIPHENOL_RAISE'),('ALKANEDIOL_BATH','ALKANEDIOL_RAISE')]:
        g['orders'].append(dict(id='O_'+left+'_'+right,kind='order',before_operation_id=left,after_operation_id=right,
            scope='acetylated_diphenol_method' if left.startswith('DIPHENOL') else 'alkanediol_method',source_fragment='diphenol_schedule' if left.startswith('DIPHENOL') else 'alkanediol_schedule',
            source_scope_approval_required=True,no_missing_initial_or_final_steps_added=True))
    f='method_comparison';base=v(f,'soluble_label1');methodA=v(f,'method_A');labelA=base+' ('+methodA+')';labelD=v(f,'soluble_label2')
    for method in ['B','C']:
        key='method'+method;label=base+' ('+v(f,key+'_letter')+')';ptr=packet['sample_anchors'][label]['pointer'];oid='METHOD_'+method
        out=oid+'_PRODUCT';identity(out,label+' reported preparation')
        g['operations'].append(dict(id=oid,kind='operation',name='polycondense source-named diol and acyl chloride',scope=label,original_sample_pointer=ptr,
            input_materials=[dict(name_raw=v(f,key+'_diol')),dict(name_raw=v(f,key+'_acyl'))],output_material_id=out,
            parameters=[par('reaction medium',f,key+'_medium')],source_fragment=f,catalyst_quantities_temperature_time_not_reported_for_this_branch=True))
        g['bindings'].append(dict(id='B_'+oid,kind='binding',operation_id=oid,output_material_id=out,original_sample_pointer=ptr,
            relation='separate_source_method_prepares_this_named2c_variant',source_fragment=f,methodA_catalyst_not_transferred=True))
        g['step_index'].append(dict(id=oid,operation_index=len(g['operations'])-1,binding_indices=[len(g['bindings'])-1]))
    low=v(f,'low_temperature');high=v(f,'high_temperature');lowstates=[];lowbind=[]
    for label in [labelA,labelD]:
        sid='LOW_TEMP_'+label.replace(' ','_');lowstates.append(sid);ptr=packet['sample_anchors'][label]['pointer']
        g['states'].append(dict(id=sid,kind='state',identity=label,original_sample_pointer=ptr,stage='after methodA preparation with final temperature limited to '+low+'°C',
            state='completely soluble product',operation_id='METHOD_A_LOW_LIMIT',source_fragment=f,independent_preparation_history=True,not_methodB_orC=True))
        g['bindings'].append(dict(id='B_'+sid,kind='binding',operation_id='METHOD_A_LOW_LIMIT',output_state_id=sid,original_sample_pointer=ptr,
            relation='this_source_methodA_product_has_the_low_final_temperature_solubility_outcome',source_fragment=f,not_shared_physical_batch=True));lowbind.append(len(g['bindings'])-1)
    g['operations'].append(dict(id='METHOD_A_LOW_LIMIT',kind='operation',name='limit final transesterification temperature',scope=[labelA,labelD],
        original_sample_pointers=[packet['sample_anchors'][x]['pointer'] for x in [labelA,labelD]],output_state_ids=lowstates,
        parameters=[par('final preparation temperature limit',f,'low_temperature','°C')],source_fragment=f,distinct_preparations_not_physical_pooling=True))
    g['step_index'].append(dict(id='METHOD_A_LOW_LIMIT',operation_index=len(g['operations'])-1,binding_indices=lowbind))
    sid='METHOD_A_HIGH_CROSSLINKED';ptr=packet['sample_anchors'][labelA]['pointer']
    g['states'].append(dict(id=sid,kind='state',identity=labelA,original_sample_pointer=ptr,stage='after the separate high-final-temperature methodA trial',
        state='product contains a small crosslinked fraction',crosslinked_fraction_raw=v(f,'crosslinked_fraction'),operation_id='METHOD_A_HIGH_TRIAL',source_fragment=f,
        uncrosslinked_remainder_not_declared_fully_crosslinked=True,outcome_fraction_not_a_processing_charge_parameter=True))
    g['operations'].append(dict(id='METHOD_A_HIGH_TRIAL',kind='operation',name='prepare source-reported higher-temperature comparison',scope=labelA,original_sample_pointer=ptr,
        output_state_id=sid,parameters=[par('final trial reaction temperature',f,'high_temperature','°C')],source_fragment=f,not_heating_the_same_low_temperature_product_again=True))
    g['bindings'].append(dict(id='B_'+sid,kind='binding',operation_id='METHOD_A_HIGH_TRIAL',output_state_id=sid,original_sample_pointer=ptr,
        relation='separate_high_temperature_trial_has_the_reported_partial_crosslink_outcome',source_fragment=f))
    g['step_index'].append(dict(id='METHOD_A_HIGH_TRIAL',operation_index=len(g['operations'])-1,binding_indices=[len(g['bindings'])-1]))
    g['bindings'].append(dict(id='B_CONTRAST_METHOD_A_TEMPERATURES',kind='binding',relation='separate_methodA_temperature_trials_have_different_reported_outcomes',
        low_temperature_state_ids=lowstates,high_temperature_state_id=sid,source_fragment=f,not_consecutive_processing_steps=True))
    labels=approval['five_anneal_scope']['annealed_labels'];observed=approval['five_anneal_scope']['no_Tg_observation_labels'];ptrs=[packet['sample_anchors'][x]['pointer'] for x in labels]
    sid='FIVE_SOURCE_SCOPE_ANNEALED';g['states'].append(dict(id=sid,kind='state',identity=labels,original_sample_pointers=ptrs,stage='after the source common65°C annealing condition',state='annealed five-series specimens',
        no_Tg_observation_sample_labels=observed,thermal_response_for5e_not_asserted=True,operation_id='FIVE_SOURCE_SCOPE_ANNEAL',source_fragment='five_anneal_scope',shared_method_variable_not_physical_pooling=True))
    g['operations'].append(dict(id='FIVE_SOURCE_SCOPE_ANNEAL',kind='operation',name='anneal the source antecedent5a–e specimen group',scope=labels,original_sample_pointers=ptrs,
        output_state_id=sid,parameters=[par('annealing temperature','five_anneal_scope','anneal_temperature','°C')],source_fragment='five_anneal_scope',duration_not_reported=True,no_Tg_result_not_extended_to5e=True))
    g['bindings'].append(dict(id='B_'+sid,kind='binding',operation_id='FIVE_SOURCE_SCOPE_ANNEAL',output_state_id=sid,original_sample_pointers=ptrs,
        relation='common_annealing_condition_and_narrower_observation_scope_kept_distinct',no_Tg_observation_sample_labels=observed,source_fragment='five_anneal_scope'))
    g['step_index'].append(dict(id='FIVE_SOURCE_SCOPE_ANNEAL',operation_index=len(g['operations'])-1,binding_indices=[len(g['bindings'])-1]))
    g['scope_notes']=['Baths and heating sequences are source method variables only. No missing initial charge, nitrogen, vacuum or workup condition is recovered here.',
        'Stepwise temperature-raising durations are not endpoint hold durations. MethodA/B/C and alternative190/210°C specimen histories are separate.',
        'The old31st-round5a–5d annealing subset remains a true subset; this source-scope repair adds5e to the common condition without adding a no-Tg result for5e.']
    return g


def main():
    packet=read(DEST/'proposal.json');rp=DEST/'source_approval.json';approval=read(rp);assert approval['proposal_sha256']==sha(DEST/'proposal.json')
    pp=OUT/'process_relation_trial_031/freeze.json';parent=read(pp);assert packet['parent_trial_freeze_sha256']==sha(pp)
    assert not (TRIAL/'freeze.json').exists();rows=[]
    for p in parent['papers']:
        assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
        if p['reference_no']==packet['reference_no']:
            pred=read(p['candidate_path']);assert EXTENSION not in pred;pred[EXTENSION]=[build(packet,approval,dict(path=str(rp),sha256=sha(rp)))];dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,pred)
            row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,
                immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
        rows.append(row)
    save(TRIAL/'freeze.json',dict(version=TRIAL.name,parent_trial='process_relation_trial_031',parent_trial_freeze_sha256=sha(pp),baseline_candidate='candidate_v10',
        baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),proposal_generation_code_sha256=sha(OUT/'propose_saved_ester_imide_method_scopes.py'),
        papers=rows,papers_total=101,changed_papers_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows),property_content_or_bindings_modified=False,
        frozen_original_outputs_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,whole_batch_reextraction=False,stable_workflow_release=False,external_api_calls=0))
    print(dict(papers=101,changed_this_round=1,old_fragments=len(packet['saved_fragments']),new_source_pages=0,scored=False))


if __name__=='__main__':main()
