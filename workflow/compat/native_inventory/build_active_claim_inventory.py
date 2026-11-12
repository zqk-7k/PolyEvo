"""Enumerate complete output containers for later source/scope/dedup review.

These are review containers, not metric units. No semantic category, source
support, or output exclusion is certified merely by being in this inventory.
"""
from pathlib import Path
import argparse
import hashlib
import json
from evaluation_integrity import reject_optimized


def canonical(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
        separators=(',',':')).encode()).hexdigest()


def inventory(prediction):
    rows=[]
    def add(path,value,role,initial_kind=None,publication='active'):
        rows.append(dict(id='C'+str(len(rows)+1).zfill(6),prediction_path=path,
            complete_container_sha256=canonical(value),role=role,initial_kind_hint=initial_kind,
            publication_boundary=publication,complete_container=value,
            scope_semantics_and_full_conjunction_not_yet_reviewed=True))
    semantic=prediction.get('active_primary_process_graph')=='source_semantic_graph'
    field='source_semantic_graph' if semantic else 'process_graph'
    graph=prediction[field]
    for key,kind in [('material_identities','binding'),('states','state'),('operations','operation'),
            ('parameters','parameter'),('orders','order'),('bindings','binding')]:
        for i,row in enumerate(graph.get(key,[])):
            add('/'+field+'/'+key+'/'+str(i),row,'primary_graph_'+key,kind)
    for key in ['nonphysical_annotations','unresolved_source_items']:
        for i,row in enumerate(graph.get(key,[])):
            add('/'+field+'/'+key+'/'+str(i),row,'source_scope_or_uncertainty_annotation',
                publication='diagnostic_or_nonphysical_claim_scope_must_be_reviewed')
    graph_metadata={'schema_version','reference_no','source_document_sha256','source_coverage'}
    graph_enumerated={'material_identities','states','operations','parameters','orders','bindings',
        'nonphysical_annotations','unresolved_source_items','native_dispositions'}
    if not semantic: graph_enumerated.remove('native_dispositions')
    for key in sorted(set(graph)-graph_metadata-graph_enumerated):
        token=key.replace('~','~0').replace('/','~1')
        add('/'+field+'/'+token,graph[key],'unclassified_graph_extension',
            publication='unclassified_extension_requires_scope_review')
    for i,row in enumerate(prediction.get('effective_process_contexts',[])):
        add('/effective_process_contexts/'+str(i),row,'full_property_owner_process_context')
    for i,row in enumerate(prediction.get('recovered_operation_history',[])):
        add('/recovered_operation_history/'+str(i),row,'active_deterministic_description_recovery')
    for i,row in enumerate(prediction.get('unconfirmed_native_claims_still_active_for_output_support',[])):
        add('/unconfirmed_native_claims_still_active_for_output_support/'+str(i),row,
            'retained_unconfirmed_native_claim')
    for i,row in enumerate(prediction.get('pending_history_recovery',[])):
        add('/pending_history_recovery/'+str(i),row,'unaccepted_diagnostic_proposal',
            publication='diagnostic_proposal_not_automatically_excluded_from_review')
    if semantic:
        add('/source_semantic_graph/native_dispositions',graph.get('native_dispositions',[]),
            'native_revision_dispositions',publication='revision_lineage_boundary_requires_review')
        add('/native_process_context',prediction.get('native_process_context',{}),
            'complete_native_revision_context',publication='revision_lineage_boundary_requires_review')
        add('/process_graph',prediction.get('process_graph',{}),'nonprimary_native_graph_boundary',
            publication='nonprimary_graph_is_not_automatically_excluded_from_review')
    else:
        add('/native_process_context',prediction.get('native_process_context',{}),'active_native_process_context')
        if 'source_semantic_graph' in prediction:
            add('/source_semantic_graph',prediction['source_semantic_graph'],'nonprimary_source_graph_boundary',
                publication='nonprimary_graph_is_not_automatically_excluded_from_review')
    root_metadata={'version','execution_mode','property_source','original_stage0_source',
        'property_values_units_sample_ids_and_bindings_unchanged',
        'all_five_reference_coverage_and_output_support_not_yet_scored','no_reference_or_score_inputs',
        'no_historical_per_paper_acceptance_inputs','complete_158_paper_specific_source_graphs_not_inherited',
        'source_location_alignment_does_not_certify_semantic_support','external_api_calls','reference_no',
        'semantic_stage_input_provenance','active_primary_process_graph',
        'native_process_context_retained_as_revision_lineage_not_second_active_graph',
        'unlisted_property_process_contexts_remain_active',
        'complete_semantic_source_support_not_certified_by_structural_validation'}
    if isinstance(prediction.get('counts'),dict) and all(isinstance(k,str) and type(v) is int and v>=0
            for k,v in prediction['counts'].items()):
        root_metadata.add('counts')
    for flag in ('source_semantic_lineage_complete','first_graph_identity_and_source_checked',
            'historical_first_capture_priority_not_independently_certified'):
        if type(prediction.get(flag)) is bool:
            root_metadata.add(flag)
    root_enumerated={'process_graph','source_semantic_graph','native_process_context','effective_process_contexts',
        'recovered_operation_history','pending_history_recovery','unconfirmed_native_claims_still_active_for_output_support'}
    for key in sorted(set(prediction)-root_metadata-root_enumerated):
        token=key.replace('~','~0').replace('/','~1')
        add('/'+token,prediction[key],'unclassified_root_extension',
            publication='unclassified_extension_requires_scope_review')
    return dict(reference_no=prediction['reference_no'],review_containers=rows,
        container_count=len(rows),not_final_deduplicated_five_dimension_denominators=True,
        every_container_requires_scope_disposition=True,
        whole_container_conjunction_may_need_multiple_dimension_units=True,
        no_unknown_claim_automatically_deleted=True,
        reference_coverage=None,output_source_support=None,external_api_calls=0)


def main():
    reject_optimized()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prediction',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): raise ValueError('Do not replace an existing inventory')
    result=inventory(json.loads(args.prediction.read_text(encoding='utf-8-sig')))
    result['prediction']=dict(path=str(args.prediction.resolve()),
        sha256=hashlib.sha256(args.prediction.read_bytes()).hexdigest())
    result['inventory_code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(reference_no=result['reference_no'],review_containers=result['container_count'],
        scientific_denominators_not_certified=True,external_api_calls=0),ensure_ascii=False))


if __name__=='__main__':
    main()
