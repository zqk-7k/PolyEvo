"""Source-approved fresh-paper contexts, composed together without scoring input."""
import argparse
from copy import deepcopy
from prepare_audit import OUT,read,save,sha,canonical


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--parent',required=True);ap.add_argument('--trial',required=True);ap.add_argument('--review',required=True)
    args=ap.parse_args();parent=OUT/args.parent;trial=OUT/args.trial;rp=OUT/args.review
    assert not trial.exists();review=read(rp);assert sha(review['code_path'])==review['code_sha256']
    cf=review['candidate_freeze_path'];assert sha(cf)==review['candidate_freeze_sha256']
    accepted={};origins={}
    for group in review['papers']:
        assert sha(group['candidate_path'])==group['candidate_sha256'];view=read(group['candidate_path'])
        by={r['owner_path']:r for r in view['effective_process_contexts']};rows=[]
        for d in group['reviewed_process_context_conjunctions']:
            assert d['conjunction_source_support']=='supported';row=by[d['owner_path']]
            assert canonical(row)==d['candidate_context_sha256'];rows.append(deepcopy(row))
        assert len(rows)==len({r['owner_path'] for r in rows})==group['reviewed_conjunction_occurrences']
        assert group['reference_no'] not in accepted;accepted[group['reference_no']]=rows;origins[group['reference_no']]=(group,view)
    pf=read(parent/'freeze.json');papers=[];changed=0
    for entry in pf['papers']:
        assert sha(entry['candidate_path'])==entry['candidate_sha256'];item=deepcopy(entry);item['changed_from_immediate_parent']=False
        ref=entry['reference_no']
        if ref in accepted:
            pred=read(entry['candidate_path']);assert 'property_process_context_revisions' not in pred
            group,view=origins[ref]
            for k in ['path','sha256']:assert pred['property_source'][k]==view['property_source'][k]
            pred['property_process_context_revisions']=dict(source_candidate_path=group['candidate_path'],source_candidate_sha256=group['candidate_sha256'],
                source_candidate_freeze_path=cf,source_candidate_freeze_sha256=sha(cf),source_acceptance_path=str(rp),source_acceptance_sha256=sha(rp),
                original_property_source=pred['property_source'],active_process_contexts=sorted(accepted[ref],key=lambda r:r['owner_path']),
                interpretation_precedence='use listed effective process contexts, including explicit whole-point parameter semantics where declared; originals retained as provenance; unlisted contexts active',
                original_property_contexts_retained_as_revision_provenance=True,unlisted_original_process_contexts_remain_active=True,
                numerical_property_outputs_and_bindings_not_rewritten=True)
            path=trial/'papers'/(ref+'.json');save(path,pred)
            item.update(candidate_path=str(path),candidate_sha256=sha(path),changed_from_parent=True,changed_from_immediate_parent=True,
                immediate_parent_candidate_path=entry['candidate_path'],immediate_parent_candidate_sha256=entry['candidate_sha256']);changed+=1
        papers.append(item)
    added=sum(map(len,accepted.values()));assert changed==len(accepted) and len(papers)==101 and added==review['reviewed_conjunction_occurrences']
    save(trial/'freeze.json',dict(version=trial.name,parent_trial=parent.name,parent_trial_freeze_sha256=sha(parent/'freeze.json'),
        baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),
        source_prediction_freeze=dict(path=cf,sha256=sha(cf)),source_acceptance=dict(path=str(rp),sha256=sha(rp)),
        prediction_composition_code_path=__file__,prediction_composition_code_sha256=sha(__file__),prediction_composition_arguments=vars(args),
        papers=papers,papers_total=101,changed_papers_this_round=changed,cumulative_changed_papers=sum(bool(p.get('changed_from_parent')) for p in papers),
        process_context_revisions_added=added,total_source_checked_context_revisions=pf['total_source_checked_context_revisions']+added,
        gain_category='existing_whole_parameter_subject_stage_and_reported_bound_repairs',new_numeric_values_extracted=0,new_source_pages_read=0,
        property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,
        whole_batch_reextraction=False,final_all_output_source_support_not_yet_scored=True,stable_workflow_release=False,external_api_calls=0))
    print(dict(trial=trial.name,changed_papers=changed,contexts_added=added,total_contexts=pf['total_source_checked_context_revisions']+added))


if __name__=='__main__':main()
