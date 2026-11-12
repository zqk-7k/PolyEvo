"""Attach an independently frozen local source supplement; property unchanged."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha

TRIAL=OUT/'process_relation_trial_024'
EXTENSION='process_targeted_page9_source_supplement'


def main():
 parentpath=OUT/'process_relation_trial_023/freeze.json';parent=read(parentpath);sf=OUT/'targeted_source_supplements/reference_no_0071536_page09/reviewed_prediction_freeze.json';source=read(sf);assert sha(source['graph_path'])==source['graph_sha256'] and sha(source['source_review_path'])==source['source_review_sha256'];graph=read(source['graph_path']);rows=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no']=='reference_no_0071536':
   new=read(p['candidate_path']);assert EXTENSION not in new;new[EXTENSION]=[dict(graph=deepcopy(graph),source_prediction_freeze_path=str(sf),source_prediction_freeze_sha256=sha(sf),source_review_path=source['source_review_path'],source_review_sha256=source['source_review_sha256'],change_class='targeted_local_primary_source_supplement_not_old_record_recovery',original_property_values_and_bindings_unchanged=True)];dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new);row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  rows.append(row)
 save(TRIAL/'freeze.json',dict(version=TRIAL.name,parent_trial='process_relation_trial_023',parent_trial_freeze_sha256=sha(parentpath),baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),source_supplement_prediction_freeze=dict(path=str(sf),sha256=sha(sf)),papers=rows,papers_total=101,changed_papers_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows),property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=1,new_pdf_information_unit='one original PDF page from one paper',new_primary_source_paragraphs=6,whole_batch_reextraction=False,stable_workflow_release=False,external_api_calls=0));print(dict(papers=101,changed_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows),new_source_pages=1,whole_batch_reextraction=False))


if __name__=='__main__':main()
