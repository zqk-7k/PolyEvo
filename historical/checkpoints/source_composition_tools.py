"""Prediction-only composition of a frozen source graph; no reference/score imports."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha,canonical


def compose(number,reference_no,extension,graph,source_prediction_freeze,source_review,identity_alignment,code_paths,**metadata):
    trial=OUT/f'process_relation_trial_{number:03d}';parent=OUT/f'process_relation_trial_{number-1:03d}'
    fp=parent/'freeze.json';pf=read(fp);assert not (trial/'freeze.json').exists()
    sf=read(source_prediction_freeze);assert sha(sf['graph_path'])==sf['graph_sha256'] and read(sf['graph_path'])==graph
    review=read(source_review);assert review['first_graph_sha256']==sf['graph_sha256'];rows=[]
    for old in pf['papers']:
        assert sha(old['candidate_path'])==old['candidate_sha256'];row=deepcopy(old);row['changed_from_immediate_parent']=False
        if old['reference_no']==reference_no:
            pred=read(old['candidate_path']);assert extension not in pred
            pred[extension]=[dict(graph=graph,source_prediction_freeze_path=str(source_prediction_freeze),source_prediction_freeze_sha256=sha(source_prediction_freeze),
                source_review_path=str(source_review),source_review_sha256=sha(source_review),identity_alignment=identity_alignment,
                no_source_graph_facts_changed_by_identity_alignment=True,property_source_and_bindings_unchanged=True)]
            dest=trial/'papers'/(reference_no+'.json');save(dest,pred)
            row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,
                immediate_parent_candidate_path=old['candidate_path'],immediate_parent_candidate_sha256=old['candidate_sha256'])
        rows.append(row)
    assert sum(x['changed_from_immediate_parent'] for x in rows)==1 and len(rows)==101
    save(trial/'freeze.json',dict(version=trial.name,parent_trial=parent.name,parent_trial_freeze_sha256=sha(fp),baseline_candidate='candidate_v10',
        baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),source_prediction_freeze=dict(path=str(source_prediction_freeze),sha256=sha(source_prediction_freeze)),
        source_review=dict(path=str(source_review),sha256=sha(source_review)),prediction_composition_code_sha256=sha(__file__),
        source_application_codes=[dict(path=str(p),sha256=sha(p)) for p in code_paths],papers=rows,papers_total=101,changed_papers_this_round=1,
        cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows),property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,
        reference_answers_or_scores_used_as_prediction_inputs=False,whole_batch_reextraction=False,stable_workflow_release=False,external_api_calls=0,**metadata))
    return trial


def verify_composition(trial,extension):
    fp=trial/'freeze.json';f=read(fp);parent=OUT/f['parent_trial'];assert sha(parent/'freeze.json')==f['parent_trial_freeze_sha256']
    assert f['prediction_composition_code_sha256']==sha(__file__)
    for code in f['source_application_codes']:assert sha(code['path'])==code['sha256']
    by={p['reference_no']:p for p in read(parent/'freeze.json')['papers']};assert len(by)==len(f['papers'])==101;changed=[]
    for p in f['papers']:
        q=by[p['reference_no']];assert sha(p['candidate_path'])==p['candidate_sha256'] and sha(q['candidate_path'])==q['candidate_sha256']
        a,b=read(p['candidate_path']),read(q['candidate_path']);assert a['property_source']==b['property_source'] and sha(a['property_source']['path'])==a['property_source']['sha256']
        if p['changed_from_immediate_parent']:
            stripped=deepcopy(a);del stripped[extension];assert stripped==b;changed.append((p,a,a[extension][0]))
        else:assert a==b
    item,=changed;p,pred,ext=item
    assert sha(ext['source_prediction_freeze_path'])==ext['source_prediction_freeze_sha256']
    s=read(ext['source_prediction_freeze_path']);assert sha(s['graph_path'])==s['graph_sha256'] and read(s['graph_path'])==ext['graph']
    assert sha(ext['source_review_path'])==ext['source_review_sha256']
    return f,item
