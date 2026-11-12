"""Derive proposals from frozen Stage3 claims and original Table1 coordinates only."""
import re
from prepare_audit import OUT,read,save,sha,canonical

DEST=OUT/'saved_cure_table_recovery'
METHOD=re.compile(r'Monomers were (?P<prepolymerization>initially polymerized) with a (?P<initial_BPO_qualifier>small amount) of (?P<initiator>benzoyl peroxide \(BPO\)) until they had an (?P<prepolymer_state>appropriate viscosity)\. In addition, (?P<addition>graded amounts of BPO were added to prepolymerized monomer), followed by (?P<coating>spin coating) \(about (?P<thickness>[\d.—–-]+)\s+(?P<thickness_unit>\$\\mu\$\s*m) in thickness\) on a (?P<substrate>glass substrate) that had a (?P<electrode>platinum electrode) deposited by the (?P<deposition>RF sputtering technique)\. The (?P<curing>thin film on the substrate was heated under various conditions)\.')
THERMAL=re.compile(r'(?P<temperature>\d+(?:\.\d+)?)\s*\((?P<duration>\d+(?:\.\d+)?)\s*(?P<duration_unit>h)\)')
RANGE=re.compile(r'(?P<minimum>\d+(?:\.\d+)?)-(?P<maximum>\d+(?:\.\d+)?)\s*(?P<unit>.+)')


def main():
 rows=[];inventory=read(OUT/'retained_stage3_prediction_inventory/manifest.json')
 for p in inventory['papers']:
  assert sha(p['path'])==p['sha256'];packet=read(p['path']);origin=packet['final_source'];assert sha(origin['path'])==origin['sha256'];doc=read(origin['path']);proposals=[]
  for step in packet['stage3_steps']:
   if step['status']=='exact_claim_body_retained_in_final':continue
   body=step['scientific_claim_body'];parameters=body.get('parameters',{})
   if body.get('process_type')!='polymerization' or set(parameters)!={'BPO','t_p'}:continue
   ranges={k:RANGE.fullmatch(v) for k,v in parameters.items()}
   if not all(ranges.values()):continue
   qchoices=[(q,METHOD.fullmatch(q['text'])) for q in packet['source_quotations'] if METHOD.fullmatch(q['text'])]
   if len(qchoices)!=1:continue
   q,m=qchoices[0];target_ids=set(body['output_sample_ids']);samples={x['sample_id']:x for x in packet['stage3_samples']};eligible=[]
   for si,series in enumerate(doc.get('property_series',[])):
    if len(series.get('points',[]))!=len(target_ids):continue
    parsed=[]
    for j,pt in enumerate(series['points']):
     labels=[c['value_raw'] for c in pt.get('coordinates',[]) if c.get('name_raw')=='source sample label'];conditions=[c['value_raw'] for c in pt.get('coordinates',[]) if c.get('name_raw')=='source condition/state']
     nums=[x for x in labels if x.isdigit()];codes=[x for x in labels if not x.isdigit()]
     thermal=[(x,list(THERMAL.finditer(x))) for x in conditions if THERMAL.search(x)];bpo=[x for x in conditions if re.fullmatch(r'\d+(?:\.\d+)?',x)]
     if len(nums)!=1 or len(codes)!=1 or len(thermal)!=1 or len(bpo)!=1:break
     candidates=[s for s in samples.values() if s['sample_id'] in target_ids and s.get('sample_label_raw')=='Sample No. '+nums[0] and s.get('polymer_name')=='Poly-'+codes[0]]
     if len(candidates)!=1:break
     raw,matches=thermal[0];remainder=THERMAL.sub('',raw).strip();sequential=len(matches)==2 and remainder in ['—','–','-'];single=len(matches)==1 and not remainder
     if not (single or sequential) or not float(ranges['BPO']['minimum'])<=float(bpo[0])<=float(ranges['BPO']['maximum']):break
     if not all(float(ranges['t_p']['minimum'])<=float(mt['temperature'])<=float(ranges['t_p']['maximum']) for mt in matches):break
     parsed.append(dict(sample_id=candidates[0]['sample_id'],sample_number_raw=nums[0],monomer_code_raw=codes[0],original_sample=candidates[0],property_point_path=f'/property_series/{si}/points/{j}',property_point_sha256=canonical(pt),thermal_coordinate_raw=raw,thermal_stages=[dict(temperature_raw=mt['temperature'],duration_raw=mt['duration'],duration_unit_raw=mt['duration_unit'],coordinate_span=list(mt.span()),capture_spans={k:list(mt.span(k)) for k in mt.groupdict()}) for mt in matches],BPO_value_raw=bpo[0],temperature_unit_raw=ranges['t_p']['unit'],BPO_unit_raw=ranges['BPO']['unit'],raw_separator=remainder,sequence_explicit_in_coordinate=sequential))
    if len(parsed)==len(target_ids) and {x['sample_id'] for x in parsed}==target_ids:eligible.append((si,parsed))
   if not eligible:continue
   si,parsed=min(eligible,key=lambda x:x[0]);proposals.append(dict(proposal_id='retained_cure_table',stage3_original_step=step,stage3_method_quote=q,method_captures={k:dict(value_raw=v,original_quote_span=list(m.span(k))) for k,v in m.groupdict().items()},parameter_headers={k:dict(original_value=parameters[k],minimum_raw=v['minimum'],maximum_raw=v['maximum'],unit_raw=v['unit'],source_path=step['original_stage3_path']+'/parameters/'+k) for k,v in ranges.items()},rows=parsed,coarse_stage3_temperature_range_not_applied_to_initial_prepolymerization=True,source_row_identity_not_same_name_matching=True))
  dest=DEST/'papers'/(p['reference_no']+'.json');save(dest,dict(reference_no=p['reference_no'],stage3_inventory_packet_path=p['path'],stage3_inventory_packet_sha256=p['sha256'],stage3_source=packet['stage3_source'],property_source=origin,proposals=proposals,reference_answers_or_scores_read=False,pdf_or_stage0_text_read=False,accepted_into_prediction=False,external_api_calls=0));rows.append(dict(reference_no=p['reference_no'],path=str(dest),sha256=sha(dest),proposals=len(proposals)))
 save(DEST/'manifest.json',dict(papers=rows,papers_scanned=len(rows),groups=sum(x['proposals'] for x in rows),generator_code_sha256=sha(__file__),reference_answers_or_scores_read=False,pdf_or_stage0_text_read=False,external_api_calls=0));print({'scanned':len(rows),'groups':sum(x['proposals'] for x in rows),'papers_with_proposals':[x['reference_no'] for x in rows if x['proposals']]})

if __name__=='__main__':main()
