"""Only frozen caption/quotation/parameter records can supply new values."""
import re
from prepare_audit import OUT,read,save,sha

DEST=OUT/'saved_polyester_thermal_variants_recovery'
PATTERNS={
 'captions6and7':re.compile(r'Fig\. 6\. DSC curves \(heating and cooling rate: (?P<scan_rate>\d+)°C/min\) of the poly\(ester-imide\) (?P<label>\w+): \(A\) heating of a sample (?P<quench_action>quenched) from (?P<quench_input>isotropic melt); \(B\) heating after (?P<cool_action_b>cooling) from the melt \((?P<melt_b>\d+)°C\) with a cooling rate of (?P<rate_b>\d+)(?P<rate_b_unit>°C/min); \(C\) heating after (?P<cool_action_c>cooling) from the melt \((?P<melt_c>\d+)°C\) with a cooling rate of (?P<rate_c>\d+)(?P<rate_c_unit>°C/min) Fig\. 7\. DSC curves \(heating and cooling rate: (?P<scan_rate7>\d+)°C/min\) of the poly\(ester-imide\) (?P<label7>\w+): \(A\) heating after (?P<anneal_action_a>annealing) for (?P<duration_a>\d+) (?P<duration_a_unit>h) at (?P<temperature_a>\d+)°C; \(B\) heating after (?P<anneal_action_b>annealing) for (?P<duration_b>\d+) (?P<duration_b_unit>min) at (?P<temperature_b>\d+)°C; \(C\) heating after (?P<anneal_action_c>annealing) for (?P<duration_c>\d+) (?P<duration_c_unit>h) at (?P<temperature_c>\d+)°C'),
 'dry_quench_response':re.compile(r'measured directly after (?P<initial>precipitation), and (?P<drying>drying) at\s+\$(?P<dry_temperature>\d+)\^\{\\circ\}\$\s*C or (?P<quenching>quenching) from the (?P<melt>isotropic melt) (?P<response>two endotherms) are observable'),
 'response_low':re.compile(r'Annealing at a temperature of\s+\$(?P<temperature>\d+)\^\{\\circ\}\$\s*C for (?P<duration>\d+) (?P<duration_unit>h) generates a DSC curve with even (?P<response>three endotherms)'),
 'response_high':re.compile(r'However, after annealing at\s+\$(?P<temperature>\d+)\^\{\\circ\}\$\s*C only (?P<response>one sharp endotherm) is detectable'),
 'caption9':re.compile(r'Fig\. 9\. DSC curves \(heating and cooling rate: (?P<scan_rate>\d+)°C/min\) of the poly\(ester-imide\) (?P<label>\w+) \(method (?P<method>\w+)\): \(A\) second heating after cooling with (?P<second_cooling_rate>\d+)°C/min; \(B\) second cooling; \(C\) (?P<measurement>third heating) after (?P<action>annealing) at (?P<temperature>\d+)°C \((?P<duration>\d+) (?P<duration_unit>min)\)')}


def main():
 rows=[]
 for p in read(OUT/'existing_evidence_recovery_inputs/manifest.json')['papers']:
  assert sha(p['path'])==p['sha256'];cache=read(p['path']);path=OUT/'candidate_v10'/(p['reference_no']+'.json');pred=read(path);origin=pred['property_source'];assert sha(origin['path'])==origin['sha256'];original=read(origin['path']);ns='native_process_context' if 'native_process_context' in pred else 'native_process_supplement';samples=pred.get(ns,{}).get('samples',[]);fragments={};proposals=[]
  for name,pattern in PATTERNS.items():
   matches=[(q,m) for q in cache['source_quotations'] if (m:=pattern.fullmatch(q['text']))]
   if len(matches)!=1:break
   q,m=matches[0];fragments[name]=dict(existing_quote=q,captures={k:dict(value_raw=v,original_quote_span=list(m.span(k))) for k,v in m.groupdict().items()})
  if len(fragments)==5:
   v=lambda g,k:fragments[g]['captures'][k]['value_raw'];label=v('captions6and7','label');methodlabel=v('caption9','label')+' ('+v('caption9','method')+')'
   targets=[dict(path=f'/{ns}/samples/{i}',sample_id=s['sample_id'],original_sample=s) for i,s in enumerate(samples) if s.get('sample_label_raw')==label];methodtargets=[dict(path=f'/{ns}/samples/{i}',sample_id=s['sample_id'],original_sample=s) for i,s in enumerate(samples) if s.get('sample_label_raw')==methodlabel]
   anchors={}
   for group in ['dry_quench_response','response_low','response_high']:
    eids={o['original_evidence_metadata'].get('evidence_id') for o in fragments[group]['existing_quote']['occurrences'] if o['source_path']==origin['path']};points=[]
    for i,s in enumerate(original.get('property_series',[])):
     for j,x in enumerate(s.get('points',[])):
      if eids.intersection(x.get('evidence_ids',[])) and any(c.get('name_raw')=='source sample label' and c.get('value_raw')==label for c in x.get('coordinates',[])):points.append(dict(path=f'/property_series/{i}/points/{j}',property_name=s.get('property_name_raw'),value_raw=x.get('value_raw'),evidence_ids=x.get('evidence_ids')))
    anchors[group]=points
   conditions=(len(targets)==len(methodtargets)==1 and v('captions6and7','label7')==label and all(anchors.values()) and v('response_low','temperature')==v('captions6and7','temperature_c') and v('response_low','duration')==v('captions6and7','duration_c') and v('response_high','temperature')==v('captions6and7','temperature_a')==v('captions6and7','temperature_b'))
   if conditions:proposals=[dict(proposal_id='source_labelled_DSC_thermal_variants',fragments=fragments,thermal_material_target=targets[0],method_specific_target=methodtargets[0],existing_property_anchors=anchors,distinct_cooling_and_annealing_conditions_not_serialized=True,caption_scan_rates_not_preparation_rates=True,reference_answers_not_generator_inputs=True)]
  dest=DEST/'papers'/(p['reference_no']+'.json');save(dest,dict(reference_no=p['reference_no'],cache_path=p['path'],cache_sha256=p['sha256'],candidate_source=dict(path=str(path),sha256=sha(path)),property_source=origin,proposals=proposals,accepted_into_prediction=False,reference_files_or_scores_used_as_generator_inputs=False,reference_seen_previously_during_error_diagnosis=True,pdf_or_stage0_source_read_by_generator=False,property_outputs_modified=False,external_api_calls=0));rows.append(dict(reference_no=p['reference_no'],path=str(dest),sha256=sha(dest),proposals=len(proposals)))
 result=dict(papers=rows,papers_scanned=len(rows),groups=sum(p['proposals'] for p in rows),generator_code_sha256=sha(__file__),reference_files_or_scores_used_as_generator_inputs=False,reference_seen_previously_during_error_diagnosis=True,pdf_or_stage0_source_read_by_generator=False,external_api_calls=0);save(DEST/'manifest.json',result);print({'papers':len(rows),'groups':result['groups'],'proposed_papers':[x['reference_no'] for x in rows if x['proposals']]})

if __name__=='__main__':main()
