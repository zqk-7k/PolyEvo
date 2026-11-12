"""Link complete native row descriptions to their own saved table, not other rows."""
import re
from prepare_audit import OUT,read,save,sha,canonical
from propose_saved_parallel_electrochemical_routes import capture

DEST=OUT/'saved_bhf_complete_recipe_links_recovery'
PATTERN=r'Carboxylic acids \(kindc\), molar ratio\): (?P<first_acid>[A-Z]+): (?P<second_acid>[A-Z]+), (?P<feed_ratio>\d+: \d+); Copolymer composition (?P<composition>\d+: \d+); (?P<diol>BHF), (?P<diol_mass>[\d.]+) mg \((?P<diol_amount>[\d.]+) mmol\); (?P<coupling_agent>DCC), (?P<coupling_mass>[\d.]+) g \((?P<coupling_amount>[\d.]+) mmol\); (?P<auxiliary>dimethylaminopyridine), (?P<auxiliary_mass>[\d.]+) mg \((?P<auxiliary_amount>[\d.]+) mmol\); (?P<solvent>1,2-dichloroethane), (?P<solvent_volume>[\d.]+) mL; (?P<temperature>room temperature), (?P<duration>[\d.]+) h\.'


def main():
 tm=OUT/'saved_bhf_condition_tables_recovery/manifest.json';tables={r['reference_no']:read(r['path'])['proposals'][0] for r in read(tm)['papers']};manifest=[];scanned=0
 for item in read(OUT/'existing_evidence_recovery_inputs/manifest.json')['papers']:
  ref=item['reference_no'];pred=read(OUT/'candidate_v10'/(ref+'.json'));scanned+=1;recipes=[]
  for i,s in enumerate(pred.get('native_process_context',{}).get('samples',[])):
   text=s.get('state_description') or ''
   if not re.fullmatch(PATTERN,text):continue
   caps=capture(text,PATTERN);assert ref in tables;table=next(t for t in tables[ref]['tables'] if t['table']=='T3');row,=[r for r in table['rows'] if r['numeric_row_label']==s['sample_label_raw'] and r['first_acid_code']==caps['first_acid']['value_raw'] and r['second_acid_code']==caps['second_acid']['value_raw'] and r['feed_ratio_raw']==caps['feed_ratio']['value_raw']];assert row['product_composition_cell']['value_raw']==caps['composition']['value_raw']
   recipes.append(dict(table='T3',row_label=s['sample_label_raw'],local_product_key=row['local_product_key'],existing_sample_pointer='/native_process_context/samples/'+str(i),existing_sample_sha256=canonical(s),existing_description_pointer='/native_process_context/samples/'+str(i)+'/state_description',existing_description=text,existing_description_sha256=canonical(text),captures=caps))
  if recipes:
   dest=DEST/'papers'/(ref+'.json');save(dest,dict(reference_no=ref,original_prediction_path=str(OUT/'candidate_v10'/(ref+'.json')),original_prediction_sha256=sha(OUT/'candidate_v10'/(ref+'.json')),saved_table_proposal_path=str(OUT/'saved_bhf_condition_tables_recovery/papers'/(ref+'.json')),saved_table_proposal_sha256=sha(OUT/'saved_bhf_condition_tables_recovery/papers'/(ref+'.json')),proposals=recipes,no_condition_transfer_to_other_rows=True,reference_answers_or_scores_read=False,source_pdf_or_stage0_read=False,external_api_calls=0));manifest.append(dict(reference_no=ref,path=str(dest),sha256=sha(dest),proposals=len(recipes)))
 save(DEST/'manifest.json',dict(papers=manifest,papers_scanned=scanned,prior_table_scan_manifest=dict(path=str(tm),sha256=sha(tm)),generator_code_sha256=sha(__file__),reference_answers_or_scores_read=False,source_pdf_or_stage0_read=False,external_api_calls=0));print(dict(scanned=scanned,proposals=sum(r['proposals'] for r in manifest)))


if __name__=='__main__':main()
