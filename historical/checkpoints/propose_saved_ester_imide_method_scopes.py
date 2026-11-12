"""Propose source-scoped reuse of actual old method and comparison sentences."""
import re
from prepare_audit import OUT,read,save,sha,canonical
from propose_saved_ester_imide_dsc_histories import cap

DEST=OUT/'saved_ester_imide_method_scopes_recovery'


def main():
    cachepath=OUT/'existing_evidence_recovery_inputs/papers/reference_no_0013464.json';cache=read(cachepath);quotes=cache['source_quotations'];frags={}
    def one(name,test,patterns):
        q,=[x for x in quotes if test(x['text'])];t=q['text'];frags[name]=dict(existing_quote=q,text_sha256=canonical(t),captures={k:cap(t,p) for k,p in patterns.items()})
    one('diphenol_heading',lambda t:t=='Polycondensation of acetylated diphenols',{'method_subject':r'Polycondensation of (.+)'})
    one('alkanediol_heading',lambda t:t.startswith('Polycondensation of') and 'omega' in t,{'method_subject':r'Polycondensation of (.+)'})
    baths=[(i,q) for i,q in enumerate(quotes) if re.fullmatch(r'The reaction vessel was placed into a metal bath preheated to \d+°C',q['text'])]
    assert len(baths)==2
    for i,(cacheindex,q) in enumerate(baths):frags['bath_'+str(i)]=dict(existing_quote=q,text_sha256=canonical(q['text']),captures={'temperature':cap(q['text'],r'preheated to (\d+)°C')},cache_order_not_source_scope_proof=True)
    one('diphenol_initiation',lambda t:'temperature was rapidly raised' in t,{'temperature':r'raised to (\d+)°C'})
    one('diphenol_schedule',lambda t:t.startswith('The temperature was then raised'),{'target':r'raised to (\d+)°C','increment':r'in steps of (\d+)°C','duration':r'period of (\d+) h'})
    one('alkanediol_schedule',lambda t:t.startswith('the temperature was raised to'),{'target':r'raised to (\d+)°C','increment':r'in steps of (\d+)°C','duration':r'period of (\d+) h'})
    one('method_comparison',lambda t:t.startswith('titanium(IV) butoxide (method A).') and len(t)>900,{
        'method_A':r'titanium\(IV\) butoxide \(method ([A-Z])\)',
        'high_temperature':r'final reaction temperature of\s+\$(\d+)\^\{\\circ\}\$ C',
        'crosslinked_label':r'fraction \([\d]+%\) of (\d+[a-z]) proved to be crosslinked',
        'crosslinked_fraction':r'fraction \((\d+%)\)',
        'low_temperature':r'limited to\s+\$(\d+)\^\{\\circ\}\$ C',
        'soluble_label1':r'resulting polyesters (\d+[a-z]) and \d+[a-z] were completely soluble',
        'soluble_label2':r'resulting polyesters \d+[a-z] and (\d+[a-z]) were completely soluble',
        'methodB_diol':r'by polycondensation of (.+?) with the acyl chloride',
        'methodB_acyl':r'by polycondensation of .+? with the (acyl chloride of \d+[a-z]) in bulk',
        'methodB_medium':r'in (bulk) \(method B\)',
        'methodB_letter':r'in bulk \(method ([A-Z])\)',
        'methodC_diol':r'Furthermore, (.+?) was polycondensed',
        'methodC_acyl':r'Furthermore, .+? was polycondensed with the (acyl chloride of \d+[a-z]) in pyridine',
        'methodC_medium':r'in (pyridine) \(method C\)',
        'methodC_letter':r'in pyridine \(method ([A-Z])\)'})
    old=read(OUT/'saved_ester_imide_dsc_histories_recovery/proposal.json')
    frags['five_anneal_scope']=old['saved_fragments']['five']
    pp=OUT/'process_relation_trial_031/freeze.json';parent=read(pp);p=next(x for x in parent['papers'] if x['reference_no']=='reference_no_0013464');assert sha(p['candidate_path'])==p['candidate_sha256']
    pred=read(p['candidate_path']);samples=pred['native_process_context']['samples'];v=lambda k:frags['method_comparison']['captures'][k]['value_raw']
    labels=[v('soluble_label1')+' ('+v('method_A')+')',v('soluble_label1')+' ('+v('methodB_letter')+')',v('soluble_label1')+' ('+v('methodC_letter')+')',v('soluble_label2')]+old['groups']['five_all'];anchors={}
    for label in labels:
        i,=[i for i,s in enumerate(samples) if s.get('sample_label_raw')==label];anchors[label]=dict(pointer='/native_process_context/samples/'+str(i),sample_sha256=canonical(samples[i]),original_sample=samples[i])
    dest=DEST/'proposal.json';assert not dest.exists();save(dest,dict(reference_no=p['reference_no'],cache_path=str(cachepath),cache_sha256=sha(cachepath),saved_fragments=frags,
        sample_anchors=anchors,five_all_labels=old['groups']['five_all'],five_no_Tg_labels=old['groups']['five_annealed'],parent_prediction_path=p['candidate_path'],parent_prediction_sha256=p['candidate_sha256'],
        parent_trial_freeze_sha256=sha(pp),old_dsc_proposal_path=str(OUT/'saved_ester_imide_dsc_histories_recovery/proposal.json'),old_dsc_proposal_sha256=sha(OUT/'saved_ester_imide_dsc_histories_recovery/proposal.json'),
        bath_role_assignment_requires_original_source_review=True,reference_answers_or_scores_read=False,new_pdf_information_extracted=0,generator_code_sha256=sha(__file__),external_api_calls=0))
    print(dict(old_fragments=len(frags),capture_spans=sum(len(x['captures']) for x in frags.values()),sample_anchors=len(anchors),source_scope_review_required=True,scored=False))


if __name__=='__main__':main()
