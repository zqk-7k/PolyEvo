"""Append source-approved contexts for a paper not previously context-revised.

Reusable source-only composer. It never reads reference items or score files.
The review approves already frozen records; it does not supply new values.
"""
import argparse
from copy import deepcopy
from prepare_audit import OUT,read,save,sha,canonical


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--parent',required=True); ap.add_argument('--trial',required=True); ap.add_argument('--review',required=True)
    args=ap.parse_args(); parent=OUT/args.parent; trial=OUT/args.trial; rp=OUT/args.review
    assert not (trial/'freeze.json').exists(); review=read(rp)
    assert sha(review['code_path'])==review['code_sha256']
    assert sha(review['candidate_path'])==review['candidate_sha256']; view=read(review['candidate_path'])
    # Locate by the reviewed candidate directory, without consulting score data.
    inferred=__import__('pathlib').Path(review['candidate_path']).parents[1]/'freeze.json'
    assert sha(inferred)==review['candidate_freeze_sha256']; cf=inferred
    by={r['owner_path']:r for r in view['effective_process_contexts']}; accepted=[]
    for d in review['reviewed_process_context_conjunctions']:
        assert d['conjunction_source_support']=='supported'; row=by[d['owner_path']]
        assert canonical(row)==d['candidate_context_sha256']; accepted.append(deepcopy(row))
    assert len(accepted)==len({r['owner_path'] for r in accepted})==review['reviewed_conjunction_occurrences']
    pf=read(parent/'freeze.json'); papers=[]; changed=0
    for p in pf['papers']:
        assert sha(p['candidate_path'])==p['candidate_sha256']; item=deepcopy(p); item['changed_from_immediate_parent']=False
        if p['reference_no']==review['reference_no']:
            pred=read(p['candidate_path']); assert 'property_process_context_revisions' not in pred
            assert pred['property_source']['path']==view['property_source']['path'] and pred['property_source']['sha256']==view['property_source']['sha256']
            pred['property_process_context_revisions']=dict(source_candidate_path=review['candidate_path'],source_candidate_sha256=review['candidate_sha256'],
                source_candidate_freeze_path=str(cf),source_candidate_freeze_sha256=sha(cf),source_acceptance_path=str(rp),source_acceptance_sha256=sha(rp),
                original_property_source=pred['property_source'],active_process_contexts=sorted(accepted,key=lambda x:x['owner_path']),
                interpretation_precedence='use listed effective process contexts; retain originals as revision provenance and all unlisted original contexts as active',
                original_property_contexts_retained_as_revision_provenance=True,unlisted_original_process_contexts_remain_active=True,
                numerical_property_outputs_and_bindings_not_rewritten=True)
            path=trial/'papers'/(p['reference_no']+'.json'); save(path,pred)
            item.update(candidate_path=str(path),candidate_sha256=sha(path),changed_from_parent=True,changed_from_immediate_parent=True,
                immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256']); changed+=1
        papers.append(item)
    assert changed==1 and len(papers)==101
    total=pf['total_source_checked_context_revisions']+len(accepted)
    save(trial/'freeze.json',dict(version=trial.name,parent_trial=parent.name,parent_trial_freeze_sha256=sha(parent/'freeze.json'),baseline_candidate='candidate_v10',
        baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),source_prediction_freeze=dict(path=str(cf),sha256=sha(cf)),
        source_acceptance=dict(path=str(rp),sha256=sha(rp)),prediction_composition_code_path=str(OUT/'compose_fresh_paper_context_trial_v1.py'),
        prediction_composition_code_sha256=sha(__file__),prediction_composition_arguments=vars(args),papers=papers,papers_total=101,
        changed_papers_this_round=1,cumulative_changed_papers=sum(bool(p.get('changed_from_parent')) for p in papers),
        process_context_revisions_added=len(accepted),total_source_checked_context_revisions=total,
        gain_category='existing_record_role_stage_subject_and_applicability_repairs',new_numeric_values_extracted=0,new_source_pages_read=0,
        property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,
        whole_batch_reextraction=False,final_all_output_source_support_not_yet_scored=True,stable_workflow_release=False,external_api_calls=0))
    print(dict(trial=trial.name,source_checked_contexts_added=len(accepted),total_source_checked_contexts=total,papers_retained=101))


if __name__=='__main__':main()
