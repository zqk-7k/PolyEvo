"""Recover source-declared LC-ionomer scopes and procedures from frozen old quotes."""
import re
from prepare_audit import OUT,read,save,sha,canonical
from current_trial_config import LATEST_PATH

DEST=OUT/'saved_lc_ionomer_routes_recovery'


def labels(text):
    out=[]
    for m in re.finditer(r'P(\d+)([abc])(?:–P(\d+)([abc]))?',text):
        if m.group(3):
            assert m.group(2)==m.group(4)
            out.extend('P'+str(i)+m.group(2) for i in range(int(m.group(1)),int(m.group(3))+1))
        else:out.append(m.group(0))
    return list(dict.fromkeys(out))


def main():
    path=OUT/'existing_evidence_recovery_inputs/papers/reference_no_0025572.json';cache=read(path);quotes=cache['source_quotations'];frags={}
    def pick(name,test,patterns):
        q,=[q for q in quotes if test(q['text']) and all(re.search(p,q['text']) for p in patterns.values())];text=q['text'];caps={}
        for key,pattern in patterns.items():
            m=re.search(pattern,text);assert m,(name,key,pattern)
            caps[key]=dict(value_raw=m.group(1),original_quote_span=list(m.span(1)))
        frags[name]=dict(existing_quote=q,text_sha256=canonical(text),captures=caps)
    pick('acid_scope',lambda t:t.startswith('The hydrolysis of the phosphonate groups'),{'inputs':r'polymers (.+?) was done','transformation':r'The (hydrolysis of the phosphonate groups)'})
    pick('acid_outputs',lambda t:t.startswith('The polymers P1b') and 'obtained in this way' in t,{'outputs':r'The polymers (.+?) obtained'})
    pick('salt_scope',lambda t:t.startswith('They were converted into the salt form'),{'outputs':r'\((P1c.+?)\)','form':r'converted into the (salt form)'})
    pick('deprotection',lambda t:t.startswith('2.5 equivalents of trimethylsilyl bromide') and len(t)>450,{
        'amount':r'^([\d.]+ equivalents) of','reagent':r'equivalents of (trimethylsilyl bromide)',
        'moisture':r'under (exclusion of moisture)','addition_temperature':r'exclusion of moisture and (room temperature)',
        'solvent':r'polymer in (abs\. dichloromethane)','stir_duration':r'mixture was stirred (\d+ h)',
        'stir_temperature':r'stirred \d+ h at (room temperature)',
        'precipitation_direction':r'precipitated by (dropping the solution into a 15-fold excess of cold methanol)',
        'precipitant':r'excess of (cold methanol)','precipitant_amount':r'into a (15-fold excess)',
        'purification_solvent':r'polymer in (chloroform)','cosolvent':r'a (small amount of methanol)',
        'reprecipitant':r'reprecipitating it in (methanol)'})
    pick('preparation_solution',lambda t:t.startswith('The polymer was dissolved in') and 'trimethylsilylbromide' in t,{'dissolution_action':r'The polymer was (dissolved)','solvent':r'in\s+\$(CH_\{2\}Cl_\{2\})\$'})
    pick('salt_method',lambda t:t.startswith('2.5 equivalents of N-ethyldimethylamine were added') and len(t)>350,{
        'amount':r'^([\d.]+ equivalents) of','reagent':r'equivalents of (N-ethyldimethylamine)',
        'inputs':r'polymer \((.+?)\) in dry','solvent':r'in (dry dichloromethane)',
        'sealing':r'After (sealing the flask)','stir_duration':r'stirred (overnight)',
        'stir_temperature':r'overnight at (room temperature)','precipitant':r'amount of (hexane)',
        'precipitant_amount':r'in a (15-fold amount)','separation':r'was (centrifuged off)',
        'drying_pressure':r'dried in (vacuum)','drying_temperature':r'at\s+\$(\d+)\^\{\\circ\}\$ C'})
    pick('layer_method',lambda t:t.startswith('At first a single layer pair') and 'Thereafter' in t,{
        'initial_pair':r'pair of (.+?) was deposited','substrate':r'on a (glass slide)',
        'subsequent_pair':r'pairs of (.+?) onto this substrate','attempt_qualifier':r'Thereafter (attempts were made)'})
    pick('buffer_condition',lambda t:t.startswith('PEI (deposited from an acidified solution)'),{'PEI_condition':r'from an (acidified solution)'})
    pick('neutral_layer_failure',lambda t:t.startswith('With the neutral LC polymer P6a'),{'label':r'polymer (P\d+[abc])','form':r'neutral LC polymer P6a \((.+?)\)','outcome':r'build-up is (clearly not possible)'})
    pick('salt_layer_success',lambda t:t.startswith('The LC ionomer P6c, on the other hand'),{'label':r'ionomer (P\d+[abc])','outcome':r'is (suitable for multilayer build-up)'})
    pick('acid_layer_success',lambda t:t.startswith('Polymer P6b with phosphonic acid units'),{'label':r'Polymer (P\d+[abc])','form':r'with (phosphonic acid units)','outcome':r'is (also suitable for a multilayer build-up)','response':r'but (less polymer gets adsorbed)'})
    pick('neutral_heating',lambda t:t.startswith('The uncharged phosphonic acid ester polymer'),{'label':r'polymer (P\d+[abc])','form':r'The (uncharged phosphonic acid ester polymer)','state':r'(flows freely on heating)'})
    pick('salt_heating',lambda t:t.startswith('On the contrary it is difficult to melt'),{'label':r'ionomer (P\d+[abc])','form':r'P6c \((.+?)\)','difficulty':r'it is (difficult to melt)','state':r'has always (a rubbery consistency)'})
    a=labels(frags['acid_scope']['captures']['inputs']['value_raw']);b=labels(frags['acid_outputs']['captures']['outputs']['value_raw'])
    c=labels(frags['salt_scope']['captures']['outputs']['value_raw']);sb=labels(frags['salt_method']['captures']['inputs']['value_raw'])
    assert len(a)==len(b)==len(c)==len(sb)==7 and b==sb
    assert [x[:-1] for x in a]==[x[:-1] for x in b]==[x[:-1] for x in c]
    pp=LATEST_PATH/'freeze.json';parent=read(pp);entry=next(x for x in parent['papers'] if x['reference_no']=='reference_no_0025572')
    assert sha(entry['candidate_path'])==entry['candidate_sha256'];pred=read(entry['candidate_path']);samples=pred['native_process_context']['samples'];anchors={}
    for label in a+b+c:
        i,=[i for i,x in enumerate(samples) if x.get('sample_label_raw')==label];anchors[label]=dict(pointer='/native_process_context/samples/'+str(i),sample_sha256=canonical(samples[i]),original_sample=samples[i])
    for alias in ['PEI','PSPM','PCM']:
        i,=[i for i,x in enumerate(samples) if '('+alias+')' in x.get('sample_label_raw','')];anchors[alias]=dict(pointer='/native_process_context/samples/'+str(i),sample_sha256=canonical(samples[i]),original_sample=samples[i])
    (layers,_),=[(i,x) for i,x in enumerate(samples) if x.get('sample_label_raw')=='multilayer structures composed of P6c and PCM']
    anchors['successful_P6c_PCM_multilayer']=dict(pointer='/native_process_context/samples/'+str(layers),sample_sha256=canonical(samples[layers]),original_sample=samples[layers])
    # The original source graph already stores the seven input/output sets.
    steps=pred['native_process_context']['process_steps'];assert steps[1]['input_sample_ids']==[samples[int(anchors[x]['pointer'].split('/')[-1])]['sample_id'] for x in a]
    dest=DEST/'proposal.json';assert not dest.exists();save(dest,dict(reference_no=entry['reference_no'],cache_path=str(path),cache_sha256=sha(path),saved_fragments=frags,
        lineages=[dict(a=x,b=y,c=z) for x,y,z in zip(a,b,c)],sample_anchors=anchors,parent_prediction_path=entry['candidate_path'],parent_prediction_sha256=entry['candidate_sha256'],
        parent_trial_freeze_path=str(pp),parent_trial_freeze_sha256=sha(pp),original_native_step_pointers=['/native_process_context/process_steps/1','/native_process_context/process_steps/2'],
        P2_and_P5_not_made_into_unreported_a_b_c_members=True,new_pdf_information_extracted=0,reference_answers_or_scores_read=False,
        generator_code_sha256=sha(__file__),source_seen_previously_for_diagnosis=True,external_api_calls=0))
    print(dict(saved_fragments=len(frags),capture_spans=sum(len(x['captures']) for x in frags.values()),independent_chemical_lineages=len(a),sample_anchors=len(anchors),new_source_pages=0,scored=False))


if __name__=='__main__':main()
