"""Compose only source-approved new owners, keeping existing array positions.

No reference, coverage verdict, or score is read. Unsupported review members
are not composed: their prior output stays active. This producer creates a
draft and cannot promote the current version or declare reference validation.
"""
import argparse
from copy import deepcopy
from prepare_audit import OUT,read,save,sha,canonical

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--parent',required=True);ap.add_argument('--trial',required=True)
    ap.add_argument('--review',required=True);args=ap.parse_args()
    parent=OUT/args.parent;dest=OUT/args.trial;rp=OUT/args.review
    assert not dest.exists();review=read(rp)
    assert sha(review['code_path'])==review['code_sha256']
    cf=review['candidate_freeze_path'];assert sha(cf)==review['candidate_freeze_sha256']
    approved={};origins={};unconfirmed=set()
    for group in review['papers']:
        assert sha(group['candidate_path'])==group['candidate_sha256'];view=read(group['candidate_path'])
        by={r['owner_path']:r for r in view['effective_process_contexts']};rows=[]
        for decision in group['reviewed_process_context_conjunctions']:
            assert decision['conjunction_source_support']=='supported'
            row=by[decision['owner_path']];assert canonical(row)==decision['candidate_context_sha256'];rows.append(deepcopy(row))
        for decision in group.get('unconfirmed_process_context_conjunctions',[]):
            assert decision['conjunction_source_support']=='unconfirmed'
            assert canonical(by[decision['owner_path']])==decision['candidate_context_sha256']
            unconfirmed.add((group['reference_no'],decision['owner_path']))
        assert len(rows)==len({r['owner_path'] for r in rows})==group['reviewed_conjunction_occurrences']
        if rows:approved[group['reference_no']]=rows;origins[group['reference_no']]=(group,view)
    pf=read(parent/'freeze.json');papers=[];events=[];added=0
    for pe in pf['papers']:
        assert sha(pe['candidate_path'])==pe['candidate_sha256'];item=deepcopy(pe);item['changed_from_immediate_parent']=False
        ref=pe['reference_no']
        if ref in approved:
            group,view=origins[ref];pred=read(pe['candidate_path'])
            for key in ['path','sha256']:assert pred['property_source'][key]==view['property_source'][key]
            assert sha(pred['property_source']['path'])==pred['property_source']['sha256']
            if 'property_process_context_revisions' not in pred:
                pred['property_process_context_revisions']=dict(source_candidate_path=group['candidate_path'],
                    source_candidate_sha256=group['candidate_sha256'],source_candidate_freeze_path=cf,
                    source_candidate_freeze_sha256=sha(cf),source_acceptance_path=str(rp),source_acceptance_sha256=sha(rp),
                    original_property_source=pred['property_source'],active_process_contexts=[],
                    interpretation_precedence='listed effective contexts take precedence for process interpretation only; originals retained as lineage; unlisted contexts active',
                    original_property_contexts_retained_as_revision_provenance=True,
                    unlisted_original_process_contexts_remain_active=True,numerical_property_outputs_and_bindings_not_rewritten=True)
            ext=pred['property_process_context_revisions'];oldrows=deepcopy(ext['active_process_contexts']);oldowners={r['owner_path'] for r in oldrows}
            newrows=sorted(approved[ref],key=lambda r:r['owner_path']);assert not oldowners.intersection(r['owner_path'] for r in newrows)
            # Keep the old prefix byte-equivalent as JSON objects. Sorting the
            # combined list would silently change existing reference pointers.
            ext['active_process_contexts']=oldrows+newrows
            newproofs=ext.setdefault('additional_source_acceptances_by_owner',{})
            for row in newrows:
                owner=row['owner_path'];assert owner not in newproofs and (ref,owner) not in unconfirmed
                newproofs[owner]=dict(source_acceptance_path=str(rp),source_acceptance_sha256=sha(rp),
                    source_candidate_path=group['candidate_path'],source_candidate_sha256=group['candidate_sha256'],
                    source_candidate_freeze_path=cf,source_candidate_freeze_sha256=sha(cf),candidate_context_sha256=canonical(row))
            event=dict(parent_trial=parent.name,parent_candidate_path=pe['candidate_path'],parent_candidate_sha256=pe['candidate_sha256'],
                old_context_prefix_count=len(oldrows),old_context_prefix_sha256=canonical(oldrows),
                appended_contexts=len(newrows),appended_owner_paths=[r['owner_path'] for r in newrows],
                previous_acceptance_metadata_and_contexts_preserved=True,source_review_path=str(rp),source_review_sha256=sha(rp))
            ext.setdefault('append_only_composition_rounds',[]).append(event)
            assert ext['active_process_contexts'][:len(oldrows)]==oldrows
            path=dest/'papers'/(ref+'.json');save(path,pred)
            item.update(candidate_path=str(path),candidate_sha256=sha(path),changed_from_parent=True,
                changed_from_immediate_parent=True,immediate_parent_candidate_path=pe['candidate_path'],
                immediate_parent_candidate_sha256=pe['candidate_sha256'])
            events.append(dict(reference_no=ref,**event));added+=len(newrows)
        papers.append(item)
    assert len(papers)==101 and len(events)==len(approved) and added==review['reviewed_conjunction_occurrences']
    save(dest/'append_only_composition.json',dict(papers=events,unconfirmed_owners_left_unmodified=[list(k) for k in sorted(unconfirmed)],
        previous_context_positions_preserved=True,source_acceptance_is_per_owner=True,
        reference_or_score_inputs_used=False,external_api_calls=0))
    save(dest/'freeze.json',dict(version=dest.name,parent_trial=parent.name,parent_trial_freeze_sha256=sha(parent/'freeze.json'),
        baseline_candidate=pf['baseline_candidate'],baseline_candidate_freeze_sha256=pf['baseline_candidate_freeze_sha256'],
        source_prediction_freeze=dict(path=cf,sha256=sha(cf)),source_acceptance=dict(path=str(rp),sha256=sha(rp)),
        prediction_composition_code_path=__file__,prediction_composition_code_sha256=sha(__file__),prediction_composition_arguments=vars(args),
        append_only_composition_sha256=sha(dest/'append_only_composition.json'),papers=papers,papers_total=101,
        changed_papers_this_round=len(events),cumulative_changed_papers=sum(bool(p.get('changed_from_parent')) for p in papers),
        process_context_revisions_added=added,total_source_checked_context_revisions=pf['total_source_checked_context_revisions']+added,
        gain_category='explicit_source_scalar_qualifier_repairs',new_numeric_values_extracted=0,new_source_pages_read=0,
        unconfirmed_new_contexts_not_accepted=len(unconfirmed),property_content_or_bindings_modified=False,
        frozen_original_outputs_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,
        whole_batch_reextraction=False,reference_validation_pending=True,output_support_register_integration_pending=True,
        final_all_output_source_support_not_yet_scored=True,stable_workflow_release=False,external_api_calls=0))
    print(dict(draft_trial=dest.name,changed_papers=len(events),contexts_appended=added,
        old_contexts_preserved=sum(e['old_context_prefix_count'] for e in events),
        unconfirmed_left_unmodified=len(unconfirmed),current_version_not_promoted=True))

if __name__=='__main__':main()
