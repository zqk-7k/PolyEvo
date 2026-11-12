"""Accept source-reviewed frozen PET/PEN contexts without reference inputs."""
from copy import deepcopy
from prepare_audit import OUT, read, save, sha, canonical


def main():
    trial = OUT / 'process_relation_trial_146'; parent = OUT / 'process_relation_trial_145'
    assert not (trial / 'freeze.json').exists()
    review_path = OUT / 'effective_process_context_source_reviews/round3_reference_no_0025765.json'
    review = read(review_path); assert sha(review['code_path']) == review['code_sha256']
    candidate_freeze = OUT / 'process_context_interpretation_candidate_v14/freeze.json'
    assert sha(candidate_freeze) == review['candidate_freeze_sha256']
    assert sha(review['candidate_path']) == review['candidate_sha256']
    view = read(review['candidate_path']); byowner = {r['owner_path']: r for r in view['effective_process_contexts']}
    accepted = []
    for decision in review['reviewed_process_context_conjunctions']:
        assert decision['conjunction_source_support'] == 'supported'
        row = byowner[decision['owner_path']]; assert canonical(row) == decision['candidate_context_sha256']
        accepted.append(deepcopy(row))
    assert len(accepted) == 378 and len({r['owner_path'] for r in accepted}) == 378
    pf = read(parent / 'freeze.json'); papers = []
    for entry in pf['papers']:
        assert sha(entry['candidate_path']) == entry['candidate_sha256']
        p = deepcopy(entry); p['changed_from_immediate_parent'] = False
        if p['reference_no'] == review['reference_no']:
            pred = read(entry['candidate_path']); assert 'property_process_context_revisions' not in pred
            assert pred['property_source']['path'] == view['property_source']['path']
            assert pred['property_source']['sha256'] == view['property_source']['sha256']
            pred['property_process_context_revisions'] = dict(source_candidate_path=review['candidate_path'],
                source_candidate_sha256=review['candidate_sha256'], source_candidate_freeze_path=str(candidate_freeze),
                source_candidate_freeze_sha256=sha(candidate_freeze), source_acceptance_path=str(review_path),
                source_acceptance_sha256=sha(review_path), original_property_source=pred['property_source'],
                active_process_contexts=sorted(accepted, key=lambda r: r['owner_path']),
                interpretation_precedence='use listed effective process subjects and contexts; original sample ID is provenance only where an explicit effective process subject is provided',
                original_property_contexts_retained_as_revision_provenance=True,
                unlisted_original_process_contexts_remain_active=True, numerical_property_outputs_and_bindings_not_rewritten=True)
            dest = trial / 'papers' / (p['reference_no'] + '.json'); save(dest, pred)
            p.update(candidate_path=str(dest), candidate_sha256=sha(dest), changed_from_parent=True,
                changed_from_immediate_parent=True, immediate_parent_candidate_path=entry['candidate_path'],
                immediate_parent_candidate_sha256=entry['candidate_sha256'])
        papers.append(p)
    assert len(papers) == 101 and sum(p['changed_from_immediate_parent'] for p in papers) == 1
    save(trial / 'freeze.json', dict(version=trial.name, parent_trial=parent.name,
        parent_trial_freeze_sha256=sha(parent / 'freeze.json'), baseline_candidate='candidate_v10',
        baseline_candidate_freeze_sha256=sha(OUT / 'candidate_v10/freeze.json'),
        source_prediction_freeze=dict(path=str(candidate_freeze), sha256=sha(candidate_freeze)),
        source_acceptance=dict(path=str(review_path), sha256=sha(review_path)),
        prediction_composition_code_path=str(OUT / 'compose_source_checked_context_trial146.py'),
        prediction_composition_code_sha256=sha(__file__), papers=papers, papers_total=101,
        changed_papers_this_round=1, cumulative_changed_papers=sum(bool(p.get('changed_from_parent')) for p in papers),
        process_context_revisions_added=378, total_source_checked_context_revisions=864,
        gain_category='existing_record_processing_subject_and_temporal_scope_repairs',
        new_numeric_values_extracted=0, new_source_pages_read=0, property_content_or_bindings_modified=False,
        frozen_original_outputs_modified=False, reference_answers_or_scores_used_as_prediction_inputs=False,
        whole_batch_reextraction=False, final_all_output_source_support_not_yet_scored=True,
        stable_workflow_release=False, external_api_calls=0))
    print(dict(trial=146, papers=101, accepted_contexts_added=378, total_accepted_contexts=864, property_outputs_unchanged=True))


if __name__ == '__main__': main()
