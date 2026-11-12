"""Rebuild actual old a→b→c and coating procedures without changing property outputs."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha
from propose_saved_lc_ionomer_routes import DEST

TRIAL=OUT/'process_relation_trial_034'
EXTENSION='process_saved_lc_ionomer_routes_recovery'


def build(packet,reviewmeta):
    g=dict(operations=[],states=[],bindings=[],orders=[],parameters=[],material_identity_nodes=[],step_index=[],
        saved_fragments=deepcopy(packet['saved_fragments']),sample_anchors=deepcopy(packet['sample_anchors']),lineages=deepcopy(packet['lineages']),
        source_approval=reviewmeta,original_property_values_and_bindings_unchanged=True,new_pdf_information_extracted=0,external_api_calls=0)
    v=lambda f,k:packet['saved_fragments'][f]['captures'][k]['value_raw']
    def par(role,f,k,unit=None,**flags):
        x=dict(role=role,value_raw=v(f,k),source_fragment=f,source_capture=k,**flags)
        if unit:x['unit_normalized']=unit
        return x
    def pointers(labels):return [packet['sample_anchors'][x]['pointer'] for x in labels]
    def material(ident,desc):g['material_identity_nodes'].append(dict(id=ident,kind='material_identity',identity=desc,initial_roster_not_a_physical_phase_assertion=True));return ident
    def add(route,step,name,inputid,frag,pars,labels,state,**flags):
        oid=route+'_'+step;sid=oid+'_STATE';inkey='input_state_id' if any(x['id']==inputid for x in g['states']) else 'input_material_id'
        op=dict(id=oid,kind='operation',name=name,scope=route,applicable_sample_labels=labels,original_sample_pointers=pointers(labels),output_state_id=sid,parameters=pars,source_fragment=frag,
                shared_method_template_not_physical_pooling=True,**flags);op[inkey]=inputid;g['operations'].append(op)
        g['states'].append(dict(id=sid,kind='state',identity=labels,original_sample_pointers=pointers(labels),stage='during/after '+name,state=state,operation_id=oid,source_fragment=frag,
            each_declared_lineage_independent=True))
        b=dict(id='B_'+oid,kind='binding',operation_id=oid,output_state_id=sid,original_sample_pointers=pointers(labels),relation='this_reported_stage_applies_separately_to_each_source_named_lineage',source_fragment=frag);b[inkey]=inputid;g['bindings'].append(b)
        g['step_index'].append(dict(route=route,step=step,operation_index=len(g['operations'])-1,state_index=len(g['states'])-1,binding_index=len(g['bindings'])-1))
        return sid
    def order(left,right,frag,**flags):
        lo=next(x for x in g['operations'] if x['id']==left);ro=next(x for x in g['operations'] if x['id']==right)
        g['orders'].append(dict(id='O_'+left+'_'+right,kind='order',before_operation_id=left,after_operation_id=right,source_fragment=frag,
            scope=lo['scope'] if lo['scope']==ro['scope'] else 'shared_buffer_method_to_specific_trial',**flags))
    aa=[x['a'] for x in packet['lineages']];bb=[x['b'] for x in packet['lineages']];cc=[x['c'] for x in packet['lineages']]
    d='deprotection';initial=material('A_PRECURSOR_IDENTITIES',aa)
    a=add(d,'DISSOLVE','dissolve the eligible phosphonate-ester polymers',initial,'preparation_solution',
        [par('dissolution solvent and source dryness','deprotection','solvent')],aa,'source a-series polymers dissolved in dichloromethane',dissolution_temperature_not_reported=True)
    a=add(d,'ADD_TMS','drop trimethylsilyl bromide into the polymer solution',a,d,
        [par('TMS bromide charge',d,'amount','equivalents',equivalent_reference_not_specified_in_saved_sentence=True),par('moisture condition',d,'moisture'),par('addition temperature description',d,'addition_temperature')],
        aa,'TMS-bromide-containing polymer reaction mixture; intermediate chemical form not asserted',unreported_N2_or_argon_not_added=True)
    a=add(d,'STIR','stir the hydrolysis-treatment reaction mixture',a,d,[par('stirring duration',d,'stir_duration','h'),par('stirring temperature description',d,'stir_temperature')],
        aa,'polymer-containing reaction mixture after the reported stirring interval; final acid form not assumed before methanol')
    a=add(d,'PRECIPITATE','drop the reaction solution into excess cold methanol',a,d,
        [par('precipitant and qualitative temperature',d,'precipitant'),par('precipitant amount',d,'precipitant_amount','fold as reported',absolute_amount_and_ratio_basis_not_inferred=True)],
        bb,'precipitated source b hydrolysis products after methanol treatment',addition_direction_is_solution_into_precipitant=True)
    a=add(d,'REDISSOLVE','redissolve the precipitated polymer in chloroform',a,d,[par('purification dissolution medium',d,'purification_solvent')],bb,'b-series polymer dissolved in chloroform')
    a=add(d,'ADD_SMALL_MEOH','add a small amount of methanol to the purification medium',a,d,[par('added cosolvent amount description',d,'cosolvent')],
        bb,'polymer-containing chloroform/methanol purification mixture',solvent_ratio_and_optical_clarity_not_reported=True)
    add(d,'REPRECIPITATE','reprecipitate the purified polymer in methanol',a,d,[par('reprecipitation medium',d,'reprecipitant')],
        bb,'reprecipitated source b phosphonate-hydrolysis products',final_drying_conditions_not_reported=True)
    seq=['DISSOLVE','ADD_TMS','STIR','PRECIPITATE','REDISSOLVE','ADD_SMALL_MEOH','REPRECIPITATE']
    for x,y in zip(seq,seq[1:]):order(d+'_'+x,d+'_'+y,d)
    g['bindings'].append(dict(id='B_A_TO_B_COMPLETE_LINEAGES',kind='binding',lineages=[dict(source_label=x['a'],product_label=x['b'],source_pointer=packet['sample_anchors'][x['a']]['pointer'],product_pointer=packet['sample_anchors'][x['b']]['pointer']) for x in packet['lineages']],
        operation_ids=[d+'_'+x for x in seq],relation='source_declared_seven_phosphonate_hydrolyses_not_all_numbered_polymers',source_fragments=['acid_scope','acid_outputs','deprotection'],P2_P5_P10_P11_not_included=True,
        methanol_treatment_not_mislabelled_as_amine_salt_formation=True))
    # A source-stated initial solution does not invent a separate dissolution action.
    s='salt_method';initial='B_INITIAL_DRY_DCM_SOLUTION';g['states'].append(dict(id=initial,kind='state',identity=bb,original_sample_pointers=pointers(bb),
        stage='reported starting solution before adding amine',state='source b polymers in dry dichloromethane',source_fragment=s,preparation_step_temperature_not_reported=True))
    a=add('salt','ADD_AMINE','add N-ethyldimethylamine to the source b-polymer solution',initial,s,
        [par('amine charge',s,'amount','equivalents',equivalent_reference_not_specified_in_saved_sentence=True),par('reaction medium and source dryness',s,'solvent')],
        bb,'amine-containing polymer reaction mixture',addition_temperature_not_independently_reported=True,covalent_quaternization_not_asserted=True)
    a=add('salt','SEAL','seal the reaction flask',a,s,[],bb,'reaction mixture in the sealed flask',vacuum_or_inert_gas_not_reported=True)
    a=add('salt','STIR','stir the sealed mixture overnight at room temperature',a,s,
        [par('stirring duration description',s,'stir_duration',numeric_hours_not_assigned=True),par('stirring temperature description',s,'stir_temperature')],bb,'source salt-formation reaction mixture after overnight stirring')
    a=add('salt','PRECIPITATE','precipitate the polymer salt in hexane',a,s,
        [par('precipitant',s,'precipitant'),par('precipitant amount',s,'precipitant_amount','fold as reported',absolute_amount_and_ratio_basis_not_inferred=True)],
        cc,'precipitated source c salt-form polymers',addition_direction_not_reported=True)
    a=add('salt','CENTRIFUGE','centrifuge off the precipitated polymer',a,s,[],cc,'separated precipitated polymer salts',centrifuge_speed_time_temperature_not_reported=True)
    add('salt','DRY','dry the isolated salt-form polymers in vacuum',a,s,
        [par('drying temperature',s,'drying_temperature','°C'),par('drying pressure description',s,'drying_pressure')],
        cc,'vacuum-dried source c ammonium-salt-form polymers',absolute_pressure_and_drying_duration_not_reported=True)
    seq=['ADD_AMINE','SEAL','STIR','PRECIPITATE','CENTRIFUGE','DRY']
    for x,y in zip(seq,seq[1:]):order('salt_'+x,'salt_'+y,s)
    g['bindings'].append(dict(id='B_B_TO_C_COMPLETE_LINEAGES',kind='binding',lineages=[dict(source_label=x['b'],product_label=x['c'],source_pointer=packet['sample_anchors'][x['b']]['pointer'],product_pointer=packet['sample_anchors'][x['c']]['pointer']) for x in packet['lineages']],
        operation_ids=['salt_'+x for x in seq],relation='source_declared_seven_b_to_c_salt_formations',source_fragments=['salt_scope','salt_method'],
        methanol_vs_hexane_and_h_vs_overnight_not_interchanged=True))
    # Common buffer method, then independent P6a/P6b/P6c comparisons.
    trials=[v('neutral_layer_failure','label'),v('acid_layer_success','label'),v('salt_layer_success','label')]
    inputs=[material('GLASS_'+label,'source glass-slide substrate method variable for '+label+' comparison') for label in trials]
    outstates=[]
    for label in trials:
        sid='BUFFERED_SUBSTRATE_'+label;outstates.append(sid);g['states'].append(dict(id=sid,kind='state',identity='glass substrate for '+label+' comparison',stage='after deposition of the initial PEI/PSPM pair',
            state='glass bearing the single source PEI/PSPM buffer-layer pair',operation_id='coating_BUFFER',source_fragment='layer_method',shared_method_scope_not_count_of_actual_slides=True))
    g['operations'].append(dict(id='coating_BUFFER',kind='operation',name='deposit one PEI/PSPM buffer-layer pair on the glass-slide substrate',scope='shared_buffer_method',
        input_material_ids=inputs,output_state_ids=outstates,input_component_identity_pointers=pointers(['PEI','PSPM']),
        parameters=[par('PEI deposition-solution condition','buffer_condition','PEI_condition')],source_fragment='layer_method',
        order_within_initial_pair_and_cleaning_not_recovered=True,shared_method_variable_for_independent_P6_trials=True))
    g['bindings'].append(dict(id='B_BUFFER_PROTOCOL',kind='binding',operation_id='coating_BUFFER',output_state_ids=outstates,component_identity_pointers=pointers(['PEI','PSPM']),
        relation='common_source_buffer_pair_precedes_each_P6_modification_trial',source_fragments=['layer_method','buffer_condition'],acidified_condition_applies_only_to_PEI=True,
        same_single_physical_slide_for_all_trials_not_asserted=True))
    g['step_index'].append(dict(route='coating',step='BUFFER',operation_index=len(g['operations'])-1,state_index=None,binding_index=len(g['bindings'])-1))
    for key,label,desc in [('neutral_layer_failure',trials[0],'no sustained multilayer build-up; no claim of absolutely zero initial adsorption'),
                           ('acid_layer_success',trials[1],'multilayer build-up is possible but less polymer gets adsorbed'),
                           ('salt_layer_success',trials[2],'source P6c/PCM multilayer build-up succeeds')]:
        oid='coating_'+label;sid=add('coating',label,'attempt further PCM/'+label+' layer pairs on the buffered substrate','BUFFERED_SUBSTRATE_'+label,'layer_method',[],[label],desc,
            source_result_fragment=key,layer_pair_partner_pointer=packet['sample_anchors']['PCM']['pointer'],order_within_pair_cycle_count_and_adsorption_times_not_reported=True,
            independent_comparison_not_a_sequence_of_P6_variants=True)
        g['states'][-1]['source_outcome']=dict(fragment=key,capture='outcome',value_raw=v(key,'outcome'))
        if key=='acid_layer_success':g['states'][-1]['relative_adsorption']=v(key,'response')
        if key=='salt_layer_success':g['bindings'][-1]['existing_output_identity_pointer']=packet['sample_anchors']['successful_P6c_PCM_multilayer']['pointer']
        order('coating_BUFFER',oid,'layer_method',applicable_buffer_state_id='BUFFERED_SUBSTRATE_'+label)
    # Qualitative bulk heating is not processing of the coated slides.
    for key in ['neutral_heating','salt_heating']:
        label=v(key,'label');inp=material('BULK_'+label,'bulk qualitative-heating specimen identity for '+label)
        add('heating_'+label,'COMPARE','heat the source-labelled bulk polymer for the qualitative flow comparison',inp,key,[],[label],v(key,'state'),
            original_sample_pointer_for_chemical_identity_only=True,not_the_coated_film_specimen=True,numerical_temperature_rate_and_stop_not_recovered=True,
            covalent_crosslinking_or_absolute_inability_to_melt_not_inferred=True)
    g['scope_notes']=['Seven independent a→b→c lineages use shared source method templates, never one physical mixture of all seven polymers.',
        'Initial source rosters are identities; the b-polymer solution is a true source-reported initial material state, without inventing a separate dissolution operation.',
        'TMS bromide hydrolysis, subsequent amine salt formation, independent coating comparisons and bulk heating are different specimen histories.',
        'No unsaved melt charges, substrate-cleaning solutions, coating concentrations, rinse steps or dip durations are supplied from source-review text.']
    return g


def main():
    pp=OUT/'process_relation_trial_033/freeze.json';parent=read(pp);packet=read(DEST/'proposal.json');rp=DEST/'source_approval.json';review=read(rp)
    assert packet['parent_trial_freeze_sha256']==sha(pp) and review['proposal_sha256']==sha(DEST/'proposal.json')
    assert not (TRIAL/'freeze.json').exists();rows=[]
    for p in parent['papers']:
        assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
        if p['reference_no']==packet['reference_no']:
            pred=read(p['candidate_path']);assert EXTENSION not in pred;pred[EXTENSION]=[build(packet,dict(path=str(rp),sha256=sha(rp)))];dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,pred)
            row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,
                immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
        rows.append(row)
    save(TRIAL/'freeze.json',dict(version=TRIAL.name,parent_trial='process_relation_trial_033',parent_trial_freeze_sha256=sha(pp),baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),
        prediction_application_code_sha256=sha(__file__),proposal_generation_code_sha256=sha(OUT/'propose_saved_lc_ionomer_routes.py'),papers=rows,papers_total=101,changed_papers_this_round=1,
        cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows),property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,
        reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,whole_batch_reextraction=False,stable_workflow_release=False,external_api_calls=0))
    print(dict(papers=101,changed_this_round=1,old_source_quotes=len(packet['saved_fragments']),new_source_pages=0,scored=False))


if __name__=='__main__':main()
