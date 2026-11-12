"""Recover method clauses and existing Table 2 coordinates, using old predictions only."""
import re
from prepare_audit import OUT,read,save,sha,canonical

DEST=OUT/'saved_blend_dsc_programs_recovery'


def captures(text,pattern):
 m=re.search(pattern,text,re.S)
 assert m,pattern
 return {k:dict(value_raw=v,original_quote_span=list(m.span(k))) for k,v in m.groupdict().items()}


def main():
 rows=[]
 for item in read(OUT/'existing_evidence_recovery_inputs/manifest.json')['papers']:
  path=item['path'];assert sha(path)==item['sha256'];cache=read(path);ref=cache['reference_no'];upath=OUT/'upstream_prediction_evidence_inventory/papers'/(ref+'.json');up=read(upath)
  pool={canonical(q['text']):q for q in cache['source_quotations']+up['new_source_quotations']}
  selectors={
   'noniso':lambda t:t.startswith('Calorimetric measurements were made with a ') and t.endswith('°C/min.') and 'The DSC cooling traces were recorded with the rates of' in t,
   'iso':lambda t:t.startswith('The DSC experiments of isothermal crystallization were carried out as follows:') and t.endswith('after complete crystallization.'),
   'melting_consumer':lambda t:t.startswith('The melting temperature ') and 'directly from' in t and t.endswith('10 deg/min.'),
   'iso_results':lambda t:t.startswith('The crystallization of LLDPE, either neat and blended ') and 'solid crystalline state' in t,
   'noniso_prehold':lambda t:t.startswith('including the preliminary ') and 'heating at' in t,
   'noniso_phase':lambda t:t=='the SBH particles remained in the crystalline state',
   'table2_header':lambda t:t.startswith('<table><tr><td>Blend</td>') and '$T_c$ (°C)' in t and '$t_{1/2}$ (sec)' in t}
  selected={k:[q for q in pool.values() if f(q['text'])] for k,f in selectors.items()};proposals=[]
  if all(len(v)==1 for v in selected.values()):
   fragments={k:dict(existing_quote=v[0],text_sha256=canonical(v[0]['text']),captures={}) for k,v in selected.items()}
   fragments['noniso']['captures']=captures(selected['noniso'][0]['text'],r'with a (?P<equipment>.*?) equipment,.*?under an (?P<atmosphere>\w+) atmosphere\. The specimens were (?P<heating>heated) to (?P<temperature>\d+)°C and (?P<holding>held) at this temperature for (?P<duration>\d+) (?P<duration_unit>min), in order to (?P<erasure>destroy the LLDPE crystal nuclei)\. The DSC (?P<cooling>cooling) traces were recorded with the rates of (?P<rate1>\d+)°, (?P<rate2>\d+)°, (?P<rate3>\d+)°, and (?P<rate4>\d+)°C/min\.')
   fragments['iso']['captures']=captures(selected['iso'][0]['text'],r'The DSC experiments of (?P<operation>isothermal crystallization).*?heated to[^\d]*(?P<temperature>\d+)[^\d]*with a rate of (?P<heating_rate>\d+) (?P<rate_unit>deg/min), held at this temperature for (?P<duration>\d+) (?P<duration_unit>min), and (?P<cooling>cooled) to.*?in the range (?P<lower>\d+)–(?P<upper>\d+)°C\) with a rate of (?P<cooling_rate>\d+) deg/min\..*?after (?P<endpoint>complete crystallization)\.')
   fragments['iso_results']['captures']=captures(selected['iso_results'][0]['text'],r'between (?P<lower>\d+) ~\s+and (?P<upper>\d+)~.*?the LCP remained in the\s+(?P<phase>solid crystalline state)')
   fragments['noniso_prehold']['captures']=captures(selected['noniso_prehold'][0]['text'],r'preliminary (?P<duration>\d+) (?P<duration_unit>min) heating at[^\d]*(?P<temperature>\d+)')
   fragments['noniso_phase']['captures']=captures(selected['noniso_phase'][0]['text'],r'(?P<material>SBH) particles remained in the (?P<phase>crystalline state)')
   fragments['melting_consumer']['captures']=captures(selected['melting_consumer'][0]['text'],r'(?P<measurement>melting temperature).*?of the (?P<input>isothermally crystallized samples).*?(?P<direct>directly from).*?with a rate of (?P<measurement_rate>\d+) (?P<measurement_rate_unit>deg/min)')
   value=lambda g,k:fragments[g]['captures'][k]['value_raw']
   assert value('noniso','temperature')==value('iso','temperature')==value('noniso_prehold','temperature')
   assert value('noniso','duration')==value('iso','duration')==value('noniso_prehold','duration')
   # These fragments require explicit source review before they may be connected.
   blocks=lambda key:{o['original_evidence_metadata'].get('block_id') for o in fragments[key]['existing_quote']['occurrences']}
   assert blocks('noniso_prehold')&blocks('noniso_phase')
   predpath=OUT/'candidate_v10'/(ref+'.json');pred=read(predpath);origin=pred['property_source'];assert sha(origin['path'])==origin['sha256'];original=read(origin['path']);ns='native_process_supplement' if 'native_process_supplement' in pred else 'native_process_context';samples=pred[ns]['samples'];pairs={};series_used=[]
   for i,s in enumerate(original['property_series']):
    if s.get('property_name_raw')!='$t_{1/2}$ (sec)':continue
    for j,p in enumerate(s.get('points',[])):
     other=p.get('measurement_context',{}).get('other_conditions',{})
     if not other.get('source_caption','').startswith('Table 2 Isothermal Crystallization Parameters'):continue
     co=p.get('coordinates',[]);labels=[x['value_raw'] for x in co if x['name_raw']=='source sample label'];temps=[x['value_raw'] for x in co if x['name_raw']=='source condition/state']
     if len(labels)!=1 or len(temps)!=1 or not re.fullmatch(r'\d+(?:\.\d+)?',temps[0]):continue
     key=(labels[0],temps[0]);matches=[(k,x) for k,x in enumerate(samples) if x.get('sample_label_raw')==labels[0]]
     if len(matches)!=1:continue
     si,sample=matches[0];record=dict(sample_label=labels[0],temperature_raw=temps[0],unit_raw='°C',unit_role_basis='Tc column in the saved Table 2 header; same Table 2 caption on retained points',existing_point_path=f'/property_series/{i}/points/{j}',original_point=p,existing_sample_path=f'/{ns}/samples/{si}',original_sample=sample)
     if key in pairs:assert pairs[key]['original_point']['value_raw']==p['value_raw']
     else:pairs[key]=record;series_used.append(i)
   assert pairs
   # Require explicit degree-C Tc series to corroborate the non-baseline coordinate role.
   explicit=[]
   for i,s in enumerate(original['property_series']):
    if s.get('property_name_raw')!='$T_c$ (°C)':continue
    for j,p in enumerate(s.get('points',[])):
     labels=[x['value_raw'] for x in p.get('coordinates',[]) if x['name_raw']=='source sample label']
     if len(labels)==1 and (labels[0],p.get('value_raw')) in pairs:explicit.append(dict(path=f'/property_series/{i}/points/{j}',original_point=p))
   assert explicit
   proposals=[dict(proposal_id='source_labelled_blend_DSC_branches',fragments=fragments,actual_isothermal_pairs=list(pairs.values()),corroborating_explicit_Tc_points=explicit,existing_sample_targets={x['sample_label']:dict(path=x['existing_sample_path'],original_sample=x['original_sample']) for x in pairs.values()},thermal_branches_are_alternatives=True,source_range_discrepancy_preserved=True,half_crystallization_times_not_processing_durations=True,fragment_connection_pending_source_review=True)]
  dest=DEST/'papers'/(ref+'.json');save(dest,dict(reference_no=ref,cache_path=path,cache_sha256=item['sha256'],upstream_cache_path=str(upath),upstream_cache_sha256=sha(upath),proposals=proposals,accepted_into_prediction=False,reference_answers_or_scores_read=False,source_pdf_or_stage0_read=False,reference_seen_previously_for_diagnosis=True,external_api_calls=0));rows.append(dict(reference_no=ref,path=str(dest),sha256=sha(dest),proposals=len(proposals)))
 save(DEST/'manifest.json',dict(papers=rows,papers_scanned=len(rows),groups=sum(x['proposals'] for x in rows),generator_code_sha256=sha(__file__),reference_answers_or_scores_read=False,source_pdf_or_stage0_read=False,external_api_calls=0));print({'scanned':len(rows),'proposed':[x['reference_no'] for x in rows if x['proposals']]})

if __name__=='__main__':main()
