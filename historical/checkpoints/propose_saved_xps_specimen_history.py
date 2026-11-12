"""Propose XPS specimen histories using actual old property coordinates only."""
import re
from prepare_audit import OUT,read,save,sha,canonical
from propose_saved_parallel_electrochemical_routes import capture

DEST=OUT/'saved_xps_specimen_history_recovery'


def main():
 manifest=[]
 for item in read(OUT/'existing_evidence_recovery_inputs/manifest.json')['papers']:
  assert sha(item['path'])==item['sha256'];cache=read(item['path']);qs=cache['source_quotations'];before=[q for q in qs if q['text'].startswith('Before the XPS analysis, the specimens were Soxhlet extracted') and '3 h' in q['text'] and 'vacuum' in q['text']];proposals=[]
  if before:
   pred=read(OUT/'candidate_v10'/(cache['reference_no']+'.json'));g=pred['process_graph'];props=pred['property_source'];assert sha(props['path'])==props['sha256'];doc=read(props['path']);byid={o['id']:(i,o) for i,o in enumerate(g['operations'])};prototypes={}
   for name,oid in [('corona','O9'),('plasma','O10'),('extraction','O12'),('degassing','O13')]:
    i,o=byid[oid];prototypes[name]=dict(pointer='/process_graph/operations/'+str(i),value_sha256=canonical(o),id=oid)
   corona_names=byid['O9'][1]['applies_to'];plasma_times=next(p['value'] for p in byid['O10'][1]['parameters'] if p['role']=='P8 XPS exposure-time alternatives');time_match=re.fullmatch(r'([\d; ]+) s',plasma_times);assert time_match;allowed_p8_times=[x.strip() for x in time_match[1].split(';')];pairs={}
   for i,series in enumerate(doc.get('property_series',[])):
    name=series.get('property_name_raw','')
    for j,point in enumerate(series.get('points',[])):
     if not re.fullmatch(r'\d+(?:\.\d+)?',str(point.get('value_raw',''))):continue
     coords=point.get('coordinates',[]);labels=[c.get('value_raw') for c in coords if c.get('name_raw')=='source sample label' and c.get('value_raw') in corona_names];captionlabels=[c.get('value_raw') for c in coords if c.get('name_raw')=='source material in table caption'];conditions=[c.get('value_raw') for c in coords if c.get('name_raw')=='source condition/state'];record=None
     if name=='Atomic C/O ratio of surface layer' and len(labels)==1:
      duration=[re.fullmatch(r'(0\.5|1|3) h',str(t)) for t in conditions];duration=[x for x in duration if x]
      if 'Corona' in conditions and len(duration)==1:record=(labels[0],'corona',duration[0][1],'h')
      elif '120 s air plasma' in conditions:record=(labels[0],'plasma','120','s')
     elif name.startswith('Intensity (%) of Si 2p peaks') and captionlabels==['material P8']:
      times=[t for t in conditions if t in allowed_p8_times]
      if len(times)==1:record=('P8','plasma',times[0],'s')
     if record:
      key=record;pairs.setdefault(key,dict(identity=record[0],exposure=record[1],duration_raw=record[2],duration_unit=record[3],actual_reported_point_anchors=[]))['actual_reported_point_anchors'].append(dict(pointer='/property_series/'+str(i)+'/points/'+str(j),value_sha256=canonical(point)))
   assert len(pairs)==25 and len([p for p in pairs if p[1]=='corona'])==15
   panel,=[q for q in qs if q['text'].startswith('Fig. 3. Advancing') and 'for the following materials:' in q['text']]
   panelcap=capture(panel['text'],r'after air plasma exposure for (?P<time1>30) s.*?(?P<time2>120) s.*?(?P<time3>180) s');contact_pairs=[]
   for name in corona_names:
    assert re.search(re.escape(name)+r' \(',panel['text'])
    for cap in panelcap.values():contact_pairs.append(dict(identity=name,exposure='plasma',duration_raw=cap['value_raw'],duration_unit='s',scope_source='saved_Fig3_caption_explicit_panels_and_legend'))
   q=max(before,key=lambda q:len(q['text']));postcap=capture(q['text'],r'extracted in\s+(?P<solvent>\$CHCl_\{3\}\$)\s+for (?P<duration>3) h.*?degassed in (?P<environment>vacuum)')
   prepared_id=byid['O7'][1]['outputs'][0];prepared,=[dict(pointer='/process_graph/states/'+str(i),value_sha256=canonical(s)) for i,s in enumerate(g['states']) if s['id']==prepared_id]
   proposals=[dict(proposal_id='saved_actual_xps_sample_exposure_histories',post_exposure_quote=q,text_sha256=canonical(q['text']),post_exposure_captures=postcap,actual_pairs=list(pairs.values()),contact_angle_panel_quote=panel,contact_angle_panel_quote_sha256=canonical(panel['text']),contact_angle_panel_captures=panelcap,contact_angle_actual_pairs=contact_pairs,existing_method_prototypes=prototypes,property_source=props,existing_network_identity_anchor=dict(pointer='/process_graph/states/0',value_sha256=canonical(g['states'][0])),existing_prepared_network_anchor=prepared,initial_pre_exposure_extraction_not_replaced=True,no_surface_fracture_specimens_included=True,contact_angle_and_XPS_specimens_not_conflated=True,requires_source_review=True,not_accepted_into_prediction=True)]
  dest=DEST/'papers'/(cache['reference_no']+'.json');save(dest,dict(reference_no=cache['reference_no'],cache_path=item['path'],cache_sha256=item['sha256'],proposals=proposals,reference_answers_or_scores_read=False,source_pdf_or_stage0_read=False,reference_seen_previously_for_diagnosis=True,external_api_calls=0));manifest.append(dict(reference_no=cache['reference_no'],path=str(dest),sha256=sha(dest),proposals=len(proposals)))
 save(DEST/'manifest.json',dict(papers=manifest,papers_scanned=len(manifest),generator_code_sha256=sha(__file__),reference_answers_or_scores_read=False,source_pdf_or_stage0_read=False,external_api_calls=0));print(dict(scanned=len(manifest),proposed=[x['reference_no'] for x in manifest if x['proposals']]))


if __name__=='__main__':main()
