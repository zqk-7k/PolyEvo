"""Join saved procedure fragments only through original evidence and sample IDs."""
import re
from prepare_audit import OUT,read,save,sha

DEST=OUT/'saved_polyaddition_workup_recovery'
PATTERNS={
 'cold':re.compile(r'The mixture was kept at (?P<temperature>-?\d+(?:\.\d+)?) (?P<temperature_unit>°C) for (?P<duration>\d+) (?P<duration_unit>min)'),
 'continuation':re.compile(r'and at (?P<temperature>room temperature) for (?P<duration>\d+) (?P<duration_unit>min) under an (?P<atmosphere>argon) atmosphere'),
 'workup':re.compile(r'The (?P<input_state>precipitated) (?P<polymer>poly\(acylurethane\)) \((?P<label>[^)]+)\) was (?P<collection>collected by filtration) and (?P<drying>dried) at (?P<temperature>\d+) (?P<temperature_unit>°C) under (?P<pressure>reduced pressure)\. Yield (?P<mass>\d+(?:\.\d+)?) (?P<mass_unit>mg) \((?P<yield>\d+(?:\.\d+)?)%, (?P<state>[^)]+)\)')}


def main():
 rows=[]
 for p in read(OUT/'candidate_v10/freeze.json')['papers']:
  pred=read(p['candidate_path']);origin=pred['property_source'];doc=read(origin['path']);cp=OUT/'existing_evidence_recovery_inputs/papers'/(p['reference_no']+'.json');cache=read(cp);proposals=[]
  series=[(i,s) for i,s in enumerate(doc.get('property_series',[])) if 'polyaddition reaction' in s.get('property_name_raw','').lower()]
  if series:
   choices={k:[(q,pattern.search(q['text'])) for q in cache['source_quotations'] if pattern.search(q['text'])] for k,pattern in PATTERNS.items()}
   if all(choices.values()):
    selected={k:min(v,key=lambda qm:len(qm[0]['text'])) for k,v in choices.items()};label=selected['workup'][1]['label']
    anchors={}
    for name in ['cold','continuation']:
     q,m=selected[name];eids={o.get('original_evidence_metadata',{}).get('evidence_id') for o in q['occurrences'] if o['source_path']==origin['path']}
     anchors[name]=[dict(path=f'/property_series/{i}/points/{j}',evidence_ids=pt.get('evidence_ids',[])) for i,s in series for j,pt in enumerate(s.get('points',[])) if any(c.get('name_raw')=='source sample label' and c.get('value_raw')==label for c in pt.get('coordinates',[])) and eids.intersection(pt.get('evidence_ids',[]))]
    if all(anchors.values()):
     locator_sets=[]
     for q,m in selected.values():locator_sets.append({(o['source_path'],o['original_evidence_metadata'].get('block_id')) for o in q['occurrences'] if o['source_path']==origin['path'] and o.get('original_evidence_metadata',{}).get('block_id')})
     shared=set.intersection(*locator_sets)
     context=pred.get('native_process_context',pred.get('native_process_supplement',{}));targets=[dict(path=('/native_process_context/' if 'native_process_context' in pred else '/native_process_supplement/')+'samples/'+str(i),sample_id=s['sample_id']) for i,s in enumerate(context.get('samples',[])) if s.get('sample_label_raw')==label]
     if shared and targets:
      fragments={k:dict(existing_quote=q,captures={n:dict(value_raw=v,original_quote_span=list(m.span(n))) for n,v in m.groupdict().items()}) for k,(q,m) in selected.items()}
      proposals.append(dict(proposal_id='linked_polyaddition_hold_and_workup',label=label,fragments=fragments,existing_property_anchors=anchors,shared_original_procedure_locators=[dict(source_path=a,block_id=b) for a,b in sorted(shared)],existing_sample_targets=targets,scope_not_expanded_to_other_table_rows=True,initial_charging_dilution_or_ether_volume_not_recovered=True))
  dest=DEST/'papers'/(p['reference_no']+'.json');save(dest,dict(reference_no=p['reference_no'],candidate_input=p,property_source=origin,cache_path=str(cp),cache_sha256=sha(cp),proposals=proposals,accepted_into_prediction=False,reference_answers_or_scores_read=False,new_pdf_information_extracted=0,external_api_calls=0));rows.append(dict(reference_no=p['reference_no'],path=str(dest),sha256=sha(dest),proposals=len(proposals)))
 save(DEST/'manifest.json',dict(papers=rows,papers_scanned=len(rows),groups=sum(x['proposals'] for x in rows),generator_code_sha256=sha(__file__),reference_answers_or_scores_read=False,external_api_calls=0));print({'scanned':len(rows),'groups':sum(x['proposals'] for x in rows),'nonempty_papers':[x['reference_no'] for x in rows if x['proposals']]})

if __name__=='__main__':main()
