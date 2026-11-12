"""Compose the separately frozen source graph; align only explicit chemical identities."""
from copy import deepcopy
import re
from prepare_audit import OUT,read,save,sha,canonical
from read_polyamide_solubility_table import DEST

TRIAL=OUT/'process_relation_trial_035'
EXTENSION='process_polyamide_source_solubility_table'


def align(pred,graph):
    out=[]
    for label in dict.fromkeys(x['sample_label'] for x in graph['states']):
        choices=[]
        for i,s in enumerate(pred['native_process_context']['samples']):
            names=[s.get('sample_label_raw'),s.get('polymer_name')]
            if any(re.fullmatch(r'(?:polyamide\s+)?'+re.escape(label),str(t or ''),re.I) for t in names):
                choices.append((i,s))
        # One synthesis-batch identity per source table label; film-state aliases are not merged.
        choices=[x for x in choices if x[1].get('sample_kind')=='synthesis_batch']
        assert len(choices)==1,(label,[(i,s.get('sample_kind')) for i,s in choices])
        i,s=choices[0];out.append(dict(source_label=label,source_material_identity_id='MATERIAL_'+label,
            original_sample_pointer='/native_process_context/samples/'+str(i),original_sample_sha256=canonical(s),
            relation='explicit_source_label_to_existing_synthesis_identity_only',
            same_physical_test_specimen_or_drying_history_not_implied=True))
    return out


def main():
    pp=OUT/'process_relation_trial_034/freeze.json';parent=read(pp);fp=DEST/'prediction_freeze.json';sf=read(fp)
    assert sha(sf['graph_path'])==sf['graph_sha256'];graph=read(sf['graph_path']);rp=DEST/'source_review.json';review=read(rp)
    assert review['first_prediction_freeze_sha256']==sha(fp) and review['graph_scientific_values_changed'] is False
    assert not (TRIAL/'freeze.json').exists();rows=[]
    for old in parent['papers']:
        assert sha(old['candidate_path'])==old['candidate_sha256'];p=deepcopy(old);p['changed_from_immediate_parent']=False
        if old['reference_no']=='reference_no_0075156':
            pred=read(old['candidate_path']);assert EXTENSION not in pred
            alignment=align(pred,graph);assert len(alignment)==12
            pred[EXTENSION]=[dict(graph=graph,source_prediction_freeze_path=str(fp),source_prediction_freeze_sha256=sha(fp),
                source_review_path=str(rp),source_review_sha256=sha(rp),identity_alignment=alignment,
                no_source_graph_facts_changed_by_identity_alignment=True,property_source_and_bindings_unchanged=True)]
            cp=TRIAL/'papers'/(old['reference_no']+'.json');save(cp,pred)
            p.update(candidate_path=str(cp),candidate_sha256=sha(cp),changed_from_parent=True,changed_from_immediate_parent=True,
                immediate_parent_candidate_path=old['candidate_path'],immediate_parent_candidate_sha256=old['candidate_sha256'])
        rows.append(p)
    save(TRIAL/'freeze.json',dict(version=TRIAL.name,parent_trial='process_relation_trial_034',parent_trial_freeze_sha256=sha(pp),
        baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),
        prediction_application_code_sha256=sha(__file__),source_prediction_freeze=dict(path=str(fp),sha256=sha(fp)),source_review=dict(path=str(rp),sha256=sha(rp)),
        papers=rows,papers_total=101,changed_papers_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows),
        property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,
        new_pdf_information_extracted=True,new_primary_source_pdf_pages_viewed=[6,7],new_primary_source_value_pages=[7],
        whole_batch_reextraction=False,stable_workflow_release=False,external_api_calls=0))
    print(dict(papers=101,changed_this_round=1,source_states=84,source_graph_unchanged=True,scored=False))


if __name__=='__main__':main()
