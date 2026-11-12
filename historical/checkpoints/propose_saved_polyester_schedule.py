"""Parse complete saved HTML condition tables; never read references or sources."""
import re
from html import unescape
from prepare_audit import OUT,read,save,sha,canonical
from propose_saved_parallel_electrochemical_routes import capture

DEST=OUT/'saved_polyester_schedule_recovery'


def plain(s):return re.sub(r'\s+',' ',unescape(re.sub('<[^>]+>','',s))).strip()


def parse_table(text):
 rows=[];current=None
 for rm in re.finditer(r'<tr>(.*?)</tr>',text,re.S):
  cells=[dict(value_raw=plain(m.group(1)),span=[rm.start(1)+m.start(1),rm.start(1)+m.end(1)]) for m in re.finditer(r'<td[^>]*>(.*?)</td>',rm.group(1),re.S)]
  if not cells:continue
  if re.fullmatch(r'(?:[234][abc]|5)',cells[0]['value_raw']):
   current=dict(label=cells[0]['value_raw'],label_span=cells[0]['span'],condition_pairs=[],viscosity_indicator=cells[4]);rows.append(current);offset=1
  elif current is not None and re.fullmatch(r'\d+(?:\s*V)?(?:,\s*\d+(?:\s*V)?)*',cells[0]['value_raw']):offset=0
  else:continue
  a,b=cells[offset:offset+2];temps=[x.strip() for x in a['value_raw'].split(',')];times=[x.strip() for x in b['value_raw'].split(',')];assert len(temps)==len(times)
  for t,h in zip(temps,times):
   assert re.fullmatch(r'\d+(?:\s*V)?',t) and re.fullmatch(r'\d+',h)
   current['condition_pairs'].append(dict(temperature_raw=t,temperature_value=re.search(r'\d+',t).group(),temperature_unit_normalized='°C',duration_raw=h,duration_unit_normalized='min',temperature_cell=a,duration_cell=b,uninterpreted_source_tag='V' if 'V' in t else None))
 return rows


def main():
 manifest=[]
 for item in read(OUT/'existing_evidence_recovery_inputs/manifest.json')['papers']:
  assert sha(item['path'])==item['sha256'];cache=read(item['path']);proposals=[]
  tables=[q for q in cache['source_quotations'] if q['text'].startswith('<table>') and 'Time in min' in q['text'] and 'Temp. in' in q['text'] and 'Insol.' in q['text'] and '320 V' in q['text']]
  workups=[q for q in cache['source_quotations'] if q['text'].startswith('The resulting polyesters were dissolved in a mixture of dichloromethane') and '120°C/12 mbar' in q['text']]
  context=[q for q in cache['source_quotations'] if q['text'].startswith('The maximum condensation temperature was limited to 320°C')]
  colors=[q for q in cache['source_quotations'] if q['text'].startswith('The polyesters obtained at temperatures ≤320°C have a yellowish or greenish color')]
  if len(tables)==len(workups)==len(context)==len(colors)==1:
   table=tables[0];rows=parse_table(table['text']);pred=read(OUT/'candidate_v10'/(cache['reference_no']+'.json'));samples=pred.get('native_process_context',{}).get('samples',[])
   anchors={s.get('sample_label_raw'):dict(pointer='/native_process_context/samples/'+str(i),sample_id=s['sample_id'],identity=s.get('polymer_name'),value_sha256=canonical(s)) for i,s in enumerate(samples) if s.get('sample_kind')=='synthesis_batch'}
   assert len(rows)==9 and sum(len(r['condition_pairs']) for r in rows)==42 and all(r['label'] in anchors for r in rows)
   for r in rows:r['existing_sample_anchor']=anchors[r['label']]
   q=workups[0];caps=capture(q['text'],r'(?P<medium>dichloromethane and trifluoroacetic acid).*?(?P<ratio>4:1).*?(?P<precipitant>methanol).*?(?P<dry_temperature>120)°C/(?P<dry_pressure>12) mbar')
   context_caps=capture(context[0]['text'],r'(?P<maximum_temperature>320)°C.*?(?P<high_temperature_result>brown or black, partially crosslinked materials)')
   color_caps=capture(colors[0]['text'],r'(?P<temperature_scope>≤320°C).*?(?P<color>yellowish or greenish color)')
   proposals=[dict(proposal_id='saved_polyester_paired_thermal_conditions_and_soluble_workup',fragments=dict(table=dict(existing_quote=table,text_sha256=canonical(table['text'])),workup=dict(existing_quote=q,text_sha256=canonical(q['text']),captures=caps),context=dict(existing_quote=context[0],text_sha256=canonical(context[0]['text']),captures=context_caps),color=dict(existing_quote=colors[0],text_sha256=canonical(colors[0]['text']),captures=color_caps)),table_rows=rows,source_tag_V_interpretation_unknown=True,temporal_order_not_inferred_from_list_positions=True,insoluble_rows_not_assigned_successful_solution_workup=True,not_accepted_into_prediction=True,requires_source_and_scope_review=True)]
  dest=DEST/'papers'/(cache['reference_no']+'.json');save(dest,dict(reference_no=cache['reference_no'],cache_path=item['path'],cache_sha256=item['sha256'],proposals=proposals,reference_answers_or_scores_read=False,source_pdf_or_stage0_read=False,reference_seen_previously_for_diagnosis=True,external_api_calls=0));manifest.append(dict(reference_no=cache['reference_no'],path=str(dest),sha256=sha(dest),proposals=len(proposals)))
 save(DEST/'manifest.json',dict(papers=manifest,papers_scanned=len(manifest),generator_code_sha256=sha(__file__),reference_answers_or_scores_read=False,source_pdf_or_stage0_read=False,external_api_calls=0));print(dict(scanned=len(manifest),proposed=[x['reference_no'] for x in manifest if x['proposals']]))


if __name__=='__main__':main()
