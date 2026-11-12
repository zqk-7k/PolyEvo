"""Recover only existing saved prose; no PDF, reference answers or scorer input."""
import re
from prepare_audit import OUT,read,save,sha,canonical
from current_trial_config import LATEST_PATH

DEST=OUT/'saved_ester_imide_dsc_histories_recovery'


def cap(text,pattern,group=1):
    m=re.search(pattern,text);assert m,pattern
    return dict(value_raw=m.group(group),original_quote_span=list(m.span(group)))


def expand(value):
    m=re.fullmatch(r'(\d+)([a-z])–(?:\1)?([a-z])',value);assert m,value
    return [m.group(1)+chr(i) for i in range(ord(m.group(2)),ord(m.group(3))+1)]


def main():
    cachepath=OUT/'existing_evidence_recovery_inputs/papers/reference_no_0013464.json';cache=read(cachepath)
    patterns={'five':lambda t:t.startswith('Differential scanning calorimetry (DSC) measurements of the poly(ester-imide)s') and len(t)>800,
              'seven':lambda t:t.startswith('DSC measurements of poly(ester-imide)') and 'same microscopic result' in t,
              'six':lambda t:t.startswith('the lower symmetry of the various diphenols') and 'annealing' in t}
    frags={}
    for key,test in patterns.items():
        q,=[x for x in cache['source_quotations'] if test(x['text'])];frags[key]=dict(existing_quote=q,text_sha256=canonical(q['text']),captures={})
    a,b,c=[frags[k]['existing_quote']['text'] for k in ['five','seven','six']]
    frags['five']['captures']={
        'group':cap(a,r'poly\(ester-imide\)s (\d+[a-z]–[a-z])'),
        'scan_rate':cap(a,r'heating rate of\s+\$(\d+)\^\{\\circ\}\$ C/min'),
        'anneal_temperature':cap(a,r'annealed at\s+\$(\d+)\^\{\\circ\}\$ C'),
        'annealed_no_Tg_group':cap(a,r'DSC curves of (\d+[a-z]–\d+[a-z])'),
        'first_cooling_label':cap(a,r'first heating curve of (\d+[a-z])'),
        'three_first_label':cap(a,r'In the case of (\d+[a-z]),'),
        'three_second_suffix':cap(a,r'In the case of \d+[a-z], ([a-z]) and [a-z]'),
        'three_third_suffix':cap(a,r'In the case of \d+[a-z], [a-z] and ([a-z])'),
        'between_endotherms':cap(a,r'(annealing between both endotherms)')}
    frags['seven']['captures']={
        'dry_label':cap(b,r'poly\(ester-imide\) (\d+[a-z]) dried at'),
        'dry_temperature':cap(b,r'dried at (\d+)°C'),
        'other_label':cap(b,r'same microscopic result was obtained for (\d+[a-z])'),
        'short_duration_description':cap(b,r'upon (short) annealing'),
        'anneal_temperature':cap(b,r'short annealing at\s+\$(\d+)\^\{\\circ\}\$ C')}
    frags['six']['captures']={'group':cap(c,r'synthesis of (\d+[a-z]–[a-z])'),
                             'anneal_temperature':cap(c,r'annealing at\s+\$(\d+)\^\{\\circ\}C\$')}
    v=lambda g,k:frags[g]['captures'][k]['value_raw']
    first=v('five','three_first_label');prefix=re.match(r'\d+',first).group()
    groups=dict(five_all=expand(v('five','group')),five_annealed=expand(v('five','annealed_no_Tg_group')),
                five_first_second=[first,prefix+v('five','three_second_suffix'),prefix+v('five','three_third_suffix')],
                cooling=[v('five','first_cooling_label')],seven_dried=[v('seven','dry_label')],seven_other=[v('seven','other_label')],
                six_annealed=expand(v('six','group')))
    parentpath=LATEST_PATH/'freeze.json';parent=read(parentpath);entry=next(x for x in parent['papers'] if x['reference_no']=='reference_no_0013464')
    assert sha(entry['candidate_path'])==entry['candidate_sha256'];pred=read(entry['candidate_path']);samples=pred['native_process_context']['samples'];anchors={}
    for label in sorted({x for rows in groups.values() for x in rows}):
        i,=[i for i,s in enumerate(samples) if s.get('sample_label_raw')==label]
        anchors[label]=dict(pointer='/native_process_context/samples/'+str(i),sample_sha256=canonical(samples[i]),original_sample=samples[i])
    p=DEST/'proposal.json';assert not p.exists();save(p,dict(reference_no=entry['reference_no'],cache_path=str(cachepath),cache_sha256=sha(cachepath),
        parent_prediction_path=entry['candidate_path'],parent_prediction_sha256=entry['candidate_sha256'],parent_trial_freeze_path=str(parentpath),parent_trial_freeze_sha256=sha(parentpath),
        saved_fragments=frags,groups=groups,sample_anchors=anchors,reference_answers_or_scores_read=False,new_pdf_information_extracted=0,
        source_seen_previously_for_diagnosis=True,external_api_calls=0,generator_code_sha256=sha(__file__)))
    print(dict(old_fragments=3,old_capture_spans=sum(len(x['captures']) for x in frags.values()),sample_labels=len(anchors),groups=groups,new_source_pages=0,scored=False))


if __name__=='__main__':main()
