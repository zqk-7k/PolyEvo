"""Append source-only process interpretation revisions; preserve all 101 originals.

Only frozen candidate records are copied. Reviews approve existing records but
provide no predicted values, sample labels, reference answers or score targets.
"""
from copy import deepcopy
from prepare_audit import OUT, read, save, sha, canonical


def main():
    trial = OUT / 'process_relation_trial_145'; parent = OUT / 'process_relation_trial_144'
    assert not (trial / 'freeze.json').exists()
    approval_path = OUT / 'source_checked_context_revisions_v1/approval.json'; approval = read(approval_path)
    assert sha(approval['code_path']) == approval['code_sha256']
    assert sha(approval['candidate_freeze_path']) == approval['candidate_freeze_sha256']
    by = {p['reference_no']: p for p in approval['papers']}; pf = read(parent / 'freeze.json')
    papers = []; count = 0
    for before in pf['papers']:
        assert sha(before['candidate_path']) == before['candidate_sha256']
        current = deepcopy(before); current['changed_from_immediate_parent'] = False
        ref = before['reference_no']
        if ref in by:
            approved = by[ref]; assert sha(approved['candidate_path']) == approved['candidate_sha256']
            raw = read(before['candidate_path']); candidate = read(approved['candidate_path'])
            assert raw['property_source']['path'] == candidate['property_source']['path']
            assert raw['property_source']['sha256'] == candidate['property_source']['sha256']
            assert sha(raw['property_source']['path']) == raw['property_source']['sha256']
            assert 'property_process_context_revisions' not in raw
            contexts = {r['owner_path']: r for r in candidate['effective_process_contexts']}
            rows = []
            for decision in approved['approved_contexts']:
                row = contexts[decision['owner_path']]
                assert canonical(row) == decision['candidate_context_sha256']
                rows.append(deepcopy(row)); count += 1
            raw['property_process_context_revisions'] = dict(
                source_candidate_path=approved['candidate_path'], source_candidate_sha256=approved['candidate_sha256'],
                source_candidate_freeze_path=approval['candidate_freeze_path'],
                source_candidate_freeze_sha256=approval['candidate_freeze_sha256'],
                source_acceptance_path=str(approval_path), source_acceptance_sha256=sha(approval_path),
                original_property_source=raw['property_source'], active_process_contexts=rows,
                interpretation_precedence='use these effective contexts for process assertions of the listed original owners',
                original_property_contexts_retained_as_revision_provenance=True,
                unlisted_original_process_contexts_remain_active=True,
                numerical_property_outputs_and_bindings_not_rewritten=True)
            dest = trial / 'papers' / (ref + '.json'); save(dest, raw)
            current.update(candidate_path=str(dest), candidate_sha256=sha(dest),
                changed_from_parent=True, changed_from_immediate_parent=True,
                immediate_parent_candidate_path=before['candidate_path'],
                immediate_parent_candidate_sha256=before['candidate_sha256'])
        papers.append(current)
    assert len(papers) == 101 and sum(p['changed_from_immediate_parent'] for p in papers) == 3 and count == 486
    save(trial / 'freeze.json', dict(version=trial.name, parent_trial=parent.name,
        parent_trial_freeze_sha256=sha(parent / 'freeze.json'), baseline_candidate='candidate_v10',
        baseline_candidate_freeze_sha256=sha(OUT / 'candidate_v10/freeze.json'),
        source_prediction_freeze=dict(path=approval['candidate_freeze_path'], sha256=approval['candidate_freeze_sha256']),
        source_acceptance=dict(path=str(approval_path), sha256=sha(approval_path)),
        prediction_composition_code_path=str(OUT / 'compose_source_checked_context_trial145_v2.py'),
        prediction_composition_code_sha256=sha(__file__), papers=papers, papers_total=101,
        changed_papers_this_round=3, cumulative_changed_papers=sum(bool(p.get('changed_from_parent')) for p in papers),
        process_context_revisions_added=486, gain_category='existing_record_role_stage_and_component_scope_repairs',
        new_numeric_values_extracted=0, new_source_pages_read=0,
        property_content_or_bindings_modified=False, frozen_original_outputs_modified=False,
        reference_answers_or_scores_used_as_prediction_inputs=False, whole_batch_reextraction=False,
        final_all_output_source_support_not_yet_scored=True, stable_workflow_release=False, external_api_calls=0))
    print(dict(trial=145, papers=101, changed_papers=3, source_checked_context_revisions=486,
        original_property_outputs_unchanged=True, final_goal_not_proven=True))


if __name__ == '__main__':
    main()
