"""Append independently frozen selected-source graph, leaving all prior fields intact."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha
from read_polysulfide_selected_procedures import DEST

TRIAL=OUT/'process_relation_trial_033'
EXTENSION='process_polysulfide_targeted_procedure_supplement'


def main():
    pp=OUT/'process_relation_trial_032/freeze.json';parent=read(pp);sf=DEST/'reviewed_prediction_freeze.json';sourcef=read(sf)
    assert sha(sourcef['graph_path'])==sourcef['graph_sha256'];graph=read(sourcef['graph_path']);rows=[]
    assert not (TRIAL/'freeze.json').exists()
    for p in parent['papers']:
        assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
        if p['reference_no']=='reference_no_0070128':
            pred=read(p['candidate_path']);assert EXTENSION not in pred
            pred[EXTENSION]=[dict(graph=deepcopy(graph),source_prediction_freeze_path=str(sf),source_prediction_freeze_sha256=sha(sf),
                source_review_path=sourcef['source_review_path'],source_review_sha256=sourcef['source_review_sha256'],
                original_property_values_and_bindings_unchanged=True,source_report_status_preserved=True)]
            dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,pred)
            row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,
                immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
        rows.append(row)
    save(TRIAL/'freeze.json',dict(version=TRIAL.name,parent_trial='process_relation_trial_032',parent_trial_freeze_sha256=sha(pp),baseline_candidate='candidate_v10',
        baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),source_prediction_freeze=dict(path=str(sf),sha256=sha(sf)),
        papers=rows,papers_total=101,changed_papers_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows),property_content_or_bindings_modified=False,
        frozen_original_outputs_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=4,
        new_pdf_information_unit='four original PDF pages, selected procedure narratives only',whole_batch_reextraction=False,stable_workflow_release=False,external_api_calls=0))
    print(dict(papers=101,changed_this_round=1,new_source_pages=4,first_source_graph_precedes_scoring=True,property_modified=False,scored=False))


if __name__=='__main__':main()
