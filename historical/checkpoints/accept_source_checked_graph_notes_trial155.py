"""Accept frozen note retyping after source review; never read reference items."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha,canonical


def main():
    root=OUT/'process_relation_trial_155';assert not root.exists()
    parent=OUT/'process_relation_trial_154/freeze.json';pf=read(parent)
    cp=OUT/'graph_note_role_retyping_candidate_v1/freeze.json';candidate=read(cp)
    rp=OUT/'graph_note_role_source_review_v2.json';review=read(rp)
    assert review['candidate_freeze_sha256']==sha(cp) and sha(review['code_path'])==review['code_sha256']
    assert review['annotation_complete_source_support']==dict(supported=3,unconfirmed=0)
    before={p['reference_no']:p for p in pf['papers']};papers=[]
    for p in candidate['papers']:
        assert sha(p['candidate_path'])==p['candidate_sha256'];item=deepcopy(p)
        old=before[p['reference_no']]
        if p['changed_from_immediate_parent']:
            pred=read(p['candidate_path']);assert pred['property_source']==read(old['candidate_path'])['property_source']
            for decision in review['decisions']:
                note=pred['process_graph']['nonphysical_annotations'][int(decision['annotation_path'].rsplit('/',1)[1])]
                assert canonical(note)==decision['annotation_sha256'] and decision['complete_annotation_source_support']=='supported'
            item.update(immediate_parent_candidate_path=old['candidate_path'],immediate_parent_candidate_sha256=old['candidate_sha256'],changed_from_parent=True)
        else:assert p['candidate_path']==old['candidate_path'] and p['candidate_sha256']==old['candidate_sha256']
        papers.append(item)
    save(root/'freeze.json',dict(version=root.name,parent_trial='process_relation_trial_154',parent_trial_freeze_sha256=sha(parent),baseline_candidate='candidate_v10',
        baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),source_prediction_freeze=dict(path=str(cp),sha256=sha(cp)),
        source_acceptance=dict(path=str(rp),sha256=sha(rp)),prediction_composition_code_path=str(OUT/'accept_source_checked_graph_notes_trial155.py'),prediction_composition_code_sha256=sha(__file__),
        papers=papers,papers_total=101,changed_papers_this_round=1,cumulative_changed_papers=sum(bool(p.get('changed_from_parent')) for p in papers),
        process_context_revisions_added=0,total_source_checked_context_revisions=pf['total_source_checked_context_revisions'],
        nonphysical_note_nodes_retyped=3,new_physical_material_states=0,new_numeric_values_extracted=0,new_source_pages_read=0,
        source_review_flags_inside_original_records_are_preserved_pre_review_provenance=True,
        gain_category='output_role_and_qualifier_witness_repair_not_new_physical_information',
        property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,
        final_all_output_source_support_not_yet_scored=True,stable_workflow_release=False,external_api_calls=0))
    print(dict(trial=root.name,source_checked_note_retypings=3,new_material_states=0,papers_retained=101))


if __name__=='__main__':main()
