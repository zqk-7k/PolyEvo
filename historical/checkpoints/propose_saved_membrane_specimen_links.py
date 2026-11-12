"""Recover old shared methods only for actually reported, source-labelled specimens."""
import re
from prepare_audit import OUT,read,save,sha,canonical
from propose_saved_parallel_electrochemical_routes import capture

DEST=OUT/'saved_membrane_specimen_links_recovery'


def choose(quotes,test,shortest=False):
 qs=[q for q in quotes if test(q['text'])]
 return (min if shortest else max)(qs,key=lambda q:len(q['text'])) if qs else None


def main():
 manifest=[]
 for item in read(OUT/'existing_evidence_recovery_inputs/manifest.json')['papers']:
  assert sha(item['path'])==item['sha256'];cache=read(item['path']);qs=cache['source_quotations'];proposals=[]
  definitions={
   'cast_head':lambda t:t.startswith('Dried sulfonated poly(aryl ether ketone) (SPAEK) that was in a sodium salt form (powder) was dissolved') and 'filter' in t,
   'cast_tail':lambda t:t.startswith('funnel. Solutions were cast onto glass plates') and 'HCl' in t,
   'uptake':lambda t:t.startswith('Before measurement, the membranes were dried') and 'Weighed films' in t,
   'conductivity':lambda t:t.startswith('The transverse proton conductivities of the acid SPAEK membranes') and '13 mm' in t and 'room temperature' in t,
   'phase':lambda t:t.startswith('Unsulfonated PAEK-NA is a semicrystalline polymer'),
   'ionic_TGA':lambda t:'The thermal stabilities of the sodium salt' in t and 'acid-form' in t and 'TGA' in t,
   'boil_failure':lambda t:'SPAEK-NA-80' in t and 'lost its mechanical proper' in t and '24 h' in t}
  selected={k:choose(qs,test,shortest=k=='boil_failure') for k,test in definitions.items()}
  if all(selected.values()):
   pred=read(OUT/'candidate_v10'/(cache['reference_no']+'.json'));g=pred['process_graph'];origin=pred['property_source'];assert sha(origin['path'])==origin['sha256'];d=read(origin['path'])
   exposure=next((x for x in g['operations'] if x['id']=='O30'),None);eligible=exposure['applies_to'];assert len(eligible)==5
   identities=[dict(identity=s['identity'],pointer='/process_graph/states/'+str(i),id=s['id'],value_sha256=canonical(s)) for i,s in enumerate(g['states']) if s['identity'] in eligible];assert len(identities)==5
   pairs={}
   for i,series in enumerate(d.get('property_series',[])):
    if not re.match('water uptake',series.get('property_name_raw',''),re.I):continue
    for j,point in enumerate(series.get('points',[])):
     coords=point.get('coordinates',[]);labels=[c.get('value_raw') for c in coords if c.get('name_raw')=='source sample label' and c.get('value_raw') in eligible]
     temps=[c.get('value_raw') for c in coords if c.get('name_raw')=='source condition/state' and re.fullmatch(r'\d+\s*°C',str(c.get('value_raw','')))]
     if not labels or not temps or not re.fullmatch(r'\d+(?:\.\d+)?',str(point.get('value_raw',''))):continue
     assert len(labels)==len(temps)==1;temp=re.search(r'\d+',temps[0]).group();key=(labels[0],temp);anchor=dict(pointer='/property_series/'+str(i)+'/points/'+str(j),value_sha256=canonical(point))
     pairs.setdefault(key,dict(identity=labels[0],temperature_raw=temp,temperature_unit_normalized='°C',actual_reported_point_anchors=[]))['actual_reported_point_anchors'].append(anchor)
   assert len(pairs)==14 and {x[0] for x in pairs}==set(eligible)
   specs={'uptake':r'(?P<weighing>Weighed films).*?(?P<length>5) mm\s*[-×\x02]\s*(?P<width>50) mm',
     'conductivity':r'(?P<diameter>13) mm\s*in diameter',
     'phase':r'Unsulfonated (?P<identity>\S+) is a (?P<phase>semicrystalline polymer)',
     'ionic_TGA':r'(?P<acid>acid-form)\s*SPAEK-NA.*?(?P<sodium>sodium salt)\s*forms',
     'boil_failure':r'(?P<identity>SPAEK-NA-80).*?(?P<outcome>lost its mechanical proper\s*ties).*?(?P<exposure>boiling in water) for (?P<duration>24) h'}
   fragments={k:dict(existing_quote=q,text_sha256=canonical(q['text']),captures=capture(q['text'],specs[k]) if k in specs else {}) for k,q in selected.items()}
   prototypes={k:[dict(pointer='/process_graph/operations/'+str(i),id=o['id'],value_sha256=canonical(o)) for i,o in enumerate(g['operations']) if o['id'] in ids] for k,ids in dict(casting=['O15','O16','O17','O18','O19','O20','O21'],uptake_drying=['O29'],conductivity_hydration=['O31'],TGA_conditioning=['O24','O25','O26']).items()}
   assert [len(prototypes[k]) for k in prototypes]==[7,1,1,3]
   state_ids=[g['operations'][14]['inputs'][0]]+[g['operations'][i]['outputs'][0] for i in range(14,21)]
   state_prototypes=[dict(pointer='/process_graph/states/'+str(i),value_sha256=canonical(s),state=s['state']) for sid in state_ids for i,s in enumerate(g['states']) if s['id']==sid]
   control,=[dict(pointer='/process_graph/states/'+str(i),value_sha256=canonical(s),identity=s['identity']) for i,s in enumerate(g['states']) if s['identity']==fragments['phase']['captures']['identity']['value_raw']]
   proposals=[dict(proposal_id='saved_actual_membrane_method_and_specimen_links',fragments=fragments,existing_individual_polymer_inputs=identities,existing_casting_state_prototypes=state_prototypes,unsulfonated_control_anchor=control,actual_uptake_pairs=list(pairs.values()),property_source=origin,existing_method_prototypes=prototypes,actual_pairs_only_not_cartesian_expansion=True,numeric_properties_not_to_be_rewritten=True,requires_source_and_scope_review=True,not_accepted_into_prediction=True)]
  dest=DEST/'papers'/(cache['reference_no']+'.json');save(dest,dict(reference_no=cache['reference_no'],cache_path=item['path'],cache_sha256=item['sha256'],proposals=proposals,reference_answers_or_scores_read=False,source_pdf_or_stage0_read=False,reference_seen_previously_for_diagnosis=True,external_api_calls=0));manifest.append(dict(reference_no=cache['reference_no'],path=str(dest),sha256=sha(dest),proposals=len(proposals)))
 save(DEST/'manifest.json',dict(papers=manifest,papers_scanned=len(manifest),generator_code_sha256=sha(__file__),reference_answers_or_scores_read=False,source_pdf_or_stage0_read=False,external_api_calls=0));print(dict(scanned=len(manifest),proposed=[x['reference_no'] for x in manifest if x['proposals']]))


if __name__=='__main__':main()
