"""Recover only conditions explicitly stored in old BHF tables, not footnotes."""
import re
from html import unescape
from prepare_audit import OUT,read,save,sha,canonical
from propose_saved_parallel_electrochemical_routes import capture

DEST=OUT/'saved_bhf_condition_tables_recovery'


def plain(text):return re.sub(r'\s+',' ',unescape(re.sub('<[^>]+>','',text))).strip()


def rows(text):
 result=[]
 for rm in re.finditer(r'<tr>(.*?)</tr>',text,re.S):
  cells=[dict(value_raw=plain(m.group(1)),span=[rm.start(1)+m.start(1),rm.start(1)+m.end(1)]) for m in re.finditer(r'<td[^>]*>(.*?)</td>',rm.group(1),re.S)]
  if not cells or not re.fullmatch(r'\d+(?:[a-z]\))?',cells[0]['value_raw']):continue
  result.append(dict(row_label=cells[0]['value_raw'],numeric_row_label=re.match(r'\d+',cells[0]['value_raw'])[0],cells=cells))
 return result


def solvent(cell):
 m=re.fullmatch(r'(?P<code>.+),\s*(?P<volume>\d+)',cell['value_raw']);assert m
 raw=m['code'];code=re.sub(r'\$\^\{[a-z]\)\}\$|[a-z]\)$','',raw)
 return dict(raw_code_and_marker=raw,code=code,volume_raw=m['volume'],volume_unit='mL',source_cell=cell,source_footnote_not_interpreted=raw!=code)


def main():
 cache_manifest=OUT/'existing_evidence_recovery_inputs/manifest.json';output=[];scanned=[]
 for item in read(cache_manifest)['papers']:
  assert sha(item['path'])==item['sha256'];cache=read(item['path']);scanned.append(dict(reference_no=cache['reference_no'],cache_sha256=item['sha256']));qs=cache['source_quotations']
  table1=[q for q in qs if q['text'].startswith('<table>') and 'DCEc), 1' in q['text'] and 'NMPf), 2' in q['text']]
  table2=[q for q in qs if q['text'].startswith('<table>') and 'Carboxylic acid (kind' in q['text'] and 'SA, 475' in q['text'] and 'TA, 464' in q['text']]
  table3=[q for q in qs if q['text'].startswith('<table>') and 'Carboxylic acids (kind' in q['text'] and 'molar ratio' in q['text'] and 'Copolymer composition' in q['text']]
  if not (len(table1)==len(table2)==len(table3)==1):continue
  acidtext=max((q for q in qs if q['text'].startswith('BHF とコハク酸ジクロリドとの重縮合結果を')),key=lambda q:len(q['text']));dcctext,=[q for q in qs if q['text'].startswith("N,N'-ジシクロヘキシルカルポジイミド(DCC)")];cotext,=[q for q in qs if q['text'].startswith('フマル酸とコハク酸の混合物，マレイン酸とコハク酸の混合物をBHF')]
  fragments={k:dict(existing_quote=q,text_sha256=canonical(q['text']),captures={}) for k,q in [('T1',table1[0]),('T2',table2[0]),('T3',table3[0]),('acid_chloride_context',acidtext),('DCC_context',dcctext),('copolyester_context',cotext)]}
  fragments['acid_chloride_context']['captures']=capture(acidtext['text'],r'(?P<diol>BHF) と(?P<acid_chloride>コハク酸ジクロリド)との(?P<polycondensation>重縮合)結果を (?P<table>Table 1)')
  fragments['DCC_context']['captures']=capture(dcctext['text'],r'(?P<coupling_agent>N,N\x27-ジシクロヘキシルカルポジイミド\((?P<coupling_code>DCC)\)).*?(?P<table>Table 2).*?(?P<diol>BHF) とコハク酸の(?P<polycondensation>重縮合)')
  fragments['copolyester_context']['captures']=capture(cotext['text'],r'(?P<feed_examples>フマル酸とコハク酸の混合物，マレイン酸とコハク酸の混合物)を(?P<diol>BHF)と(?P<polycondensation>重縮合).*?(?P<table>Table3)')
  tables=[]
  for key,q in [('T1',table1[0]),('T2',table2[0]),('T3',table3[0])]:
   data=rows(q['text'])
   for row in data:
    row['local_product_key']=key+'_RUN_'+row['numeric_row_label']
    if key in ['T1','T2']:row['solvent']=solvent(row['cells'][1 if key=='T1' else 2])
    if key=='T2':
     m=re.fullmatch(r'(?P<acid>[A-Z]+),\s*(?P<mass>\d+)',row['cells'][1]['value_raw']);assert m;row['acid_code']=m['acid'];row['acid_mass_raw']=m['mass'];row['acid_mass_unit']='mg'
    if key=='T3':
     m=re.fullmatch(r'(?P<first>[A-Z]+):\s*(?P<second>[A-Z]+),\s*(?P<ratio>\d+:\s*\d+)',row['cells'][1]['value_raw']);assert m;row.update(first_acid_code=m['first'],second_acid_code=m['second'],feed_ratio_raw=m['ratio'],feed_ratio_unit='molar ratio',product_composition_cell=row['cells'][4],product_composition_is_not_feed=True)
   tables.append(dict(table=key,rows=data))
  assert [len(t['rows']) for t in tables]==[11,10,4]
  p=dict(proposal_id='saved_BHF_route_separated_table_conditions',fragments=fragments,tables=tables,footnote_conditions_unknown=True,acid_abbreviations_retained_without_guessing_global_meanings=True,no_material_state_inferred_from_polymer_identity=True,no_shared_charge_temperature_time_or_catalyst_amount_inferred=True,not_accepted_into_prediction=True,requires_source_review=True)
  dest=DEST/'papers'/(cache['reference_no']+'.json');save(dest,dict(reference_no=cache['reference_no'],cache_path=item['path'],cache_sha256=item['sha256'],proposals=[p],reference_answers_or_scores_read=False,source_pdf_or_stage0_read=False,reference_seen_previously_for_diagnosis=True,external_api_calls=0));output.append(dict(reference_no=cache['reference_no'],path=str(dest),sha256=sha(dest),proposals=1))
 save(DEST/'manifest.json',dict(papers=output,papers_scanned=len(scanned),scanned_cache_manifest_path=str(cache_manifest),scanned_cache_manifest_sha256=sha(cache_manifest),scanned_papers=scanned,generator_code_sha256=sha(__file__),blank_per_paper_proposal_files_not_created=True,reference_answers_or_scores_read=False,source_pdf_or_stage0_read=False,external_api_calls=0));print(dict(scanned=len(scanned),proposed=[r['reference_no'] for r in output]))


if __name__=='__main__':main()
