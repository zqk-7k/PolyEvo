"""Parse a complete saved casting method and align explicit native batch/film names."""
import re
from copy import deepcopy
from prepare_audit import OUT,read,save,sha,canonical

DEST=OUT/'saved_solution_casting_chain_recovery'


def chemical_label(sample):
    raw=sample.get('sample_label_raw') or sample.get('polymer_name') or ''
    return re.sub(r'^polyamide\s+','',raw,flags=re.I).strip()


def extract_clause_captures(text):
    patterns={
        'polymer_mass':r'dissolving\s+(about\s+[0-9.]+)\s*g',
        'solvent_volume':r'polymer\s+in\s+([0-9.]+)\s*mL',
        'dissolution_medium':r'mL\s+of\s+(hot\s+DMAc\s+or\s+NMP)',
        'solution_concentration':r'an\s+(approximate\s+[0-9.]+)\s*wt\s*%',
        'dish_diameter':r'into\s+a\s+([0-9.]+)-cm\s+diameter\s+glass\s+culture\s+dish',
        'evaporation_temperature':r'in\s+a\s+([0-9.]+)°C\s+oven',
        'evaporation_duration':r'oven\s+(overnight)',
        'drying_pressure':r'further\s+dried\s+(in\s+vacuo)',
        'drying_temperature':r'in\s+vacuo\s+at\s+([0-9.]+)°C',
        'drying_duration':r'at\s+[0-9.]+°C\s+for\s+([0-9.]+)\s*h'}
    captures={}
    for key,pattern in patterns.items():
        found=list(re.finditer(pattern,text,re.I));assert len(found)==1,(key,len(found))
        m=found[0];captures[key]=dict(value_raw=m.group(1),original_quote_span=list(m.span(1)))
    assert 'clear solution was poured' in text.lower() and 'semidried' in text.lower() and 'stripped off' in text.lower()
    return captures


def main():
    assert not (DEST/'proposal.json').exists()
    pp=OUT/'process_relation_trial_035/freeze.json';f=read(pp);proposals=[];scanned=0
    # The scan uses only stored prediction evidence, not PDF/Stage0 or references.
    for entry in f['papers']:
        cp=OUT/'existing_evidence_recovery_inputs/papers'/(entry['reference_no']+'.json');c=read(cp);scanned+=1
        for q in c['source_quotations']:
            t=q['text'].lower()
            if not all(w in t for w in ['dissolving','poured','semidried','stripped off','in vacuo']):continue
            captures=extract_clause_captures(q['text']);pred=read(entry['candidate_path']);ctx=pred['native_process_context']
            steps=[(i,s) for i,s in enumerate(ctx['process_steps']) if s.get('process_type')=='casting']
            assert len(steps)==1;index,step=steps[0];samples={s['sample_id']:(i,s) for i,s in enumerate(ctx['samples'])};lineages=[]
            for inputid in step['input_sample_ids']:
                ai,a=samples[inputid];label=chemical_label(a)
                bs=[samples[z] for z in step['output_sample_ids'] if chemical_label(samples[z][1])==label]
                assert len(bs)==1,(entry['reference_no'],inputid,label)
                bi,b=bs[0];lineages.append(dict(label=label,input_sample_pointer='/native_process_context/samples/'+str(ai),input_sample_sha256=canonical(a),
                    output_sample_pointer='/native_process_context/samples/'+str(bi),output_sample_sha256=canonical(b),
                    input_kind=a['sample_kind'],output_kind=b['sample_kind'],name_match_without_array_position_inference=True))
            assert len(lineages)==len(step['output_sample_ids']) and len(set(x['label'] for x in lineages))==len(lineages)
            assert step['parameters']['film_thickness']
            proposals.append(dict(reference_no=entry['reference_no'],cache_path=str(cp),cache_sha256=sha(cp),saved_quote=deepcopy(q),captures=captures,
                native_casting_step_pointer='/native_process_context/process_steps/'+str(index),native_casting_step_sha256=canonical(step),lineages=lineages,
                native_film_thickness=dict(pointer='/native_process_context/process_steps/'+str(index)+'/parameters/film_thickness',value_raw=step['parameters']['film_thickness']),
                parent_prediction_path=entry['candidate_path'],parent_prediction_sha256=entry['candidate_sha256']))
    assert len(proposals)==1 and proposals[0]['reference_no']=='reference_no_0075156'
    save(DEST/'proposal.json',dict(proposals=proposals,papers_scanned=scanned,parent_trial_freeze_path=str(pp),parent_trial_freeze_sha256=sha(pp),
        generator_code_sha256=sha(__file__),source_pdf_or_Stage0_read=False,new_primary_source_values=0,reference_answers_or_scores_read=False,
        prior_developer_context_has_seen_diagnosis=True,no_independent_or_hard_isolation_claim=True,external_api_calls=0))
    print(dict(saved_complete_methods=len(proposals),papers_scanned=scanned,captured_values=len(proposals[0]['captures']),lineages=len(proposals[0]['lineages']),scored=False))


if __name__=='__main__':main()
