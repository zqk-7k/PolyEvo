"""Read frozen predictions only; propose explicitly saved qualitative medium states."""
import re
from prepare_audit import OUT,read,save,sha,canonical
from propose_saved_parallel_electrochemical_routes import capture

DEST=OUT/'saved_polyamide_medium_states_recovery'


def main():
 rows=[]
 for item in read(OUT/'existing_evidence_recovery_inputs/manifest.json')['papers']:
  assert sha(item['path'])==item['sha256'];cache=read(item['path']);proposals=[]
  resistant=[q for q in cache['source_quotations'] if 'all of them were resistant to com-' in q['text'] and 'tetrahydrofuran' in q['text'] and 'alcohols' in q['text']]
  negative=[q for q in cache['source_quotations'] if q['text'].startswith('A combination of meta- and para-oriented') and 'no liquid crystalline polymer/ solvent system was observed' in q['text']]
  if len(resistant)==len(negative)==1:
   pred=read(OUT/'candidate_v10'/(cache['reference_no']+'.json'));g=pred.get('process_graph',{})
   inputs=[dict(pointer='/process_graph/states/'+str(i),id=s['id'],identity=s['identity'],value_sha256=canonical(s)) for i,s in enumerate(g.get('states',[])) if re.fullmatch(r'dry_\d+',s['id']) and 'Independently isolated polymer after ethanol washing' in s.get('state','')]
   if len(inputs)==9 and len({x['identity'] for x in inputs})==9:
    q=resistant[0];a=capture(q['text'],r'(?P<response>resistant).*?(?P<medium_THF>tetrahydrofuran),\s*(?P<medium_CHCl3>chloro-\s*form),\s*or (?P<medium_alcohols>alcohols)')
    n=negative[0];b=capture(n['text'],r'(?P<negative_phase>no liquid crystalline polymer/ solvent system was observed).*?(?P<scope>manipulation of solutions)')
    proposals=[dict(proposal_id='saved_polyamide_qualitative_medium_states',fragments=dict(resistance=dict(existing_quote=q,text_sha256=canonical(q['text']),captures=a),negative_phase=dict(existing_quote=n,text_sha256=canonical(n['text']),captures=b)),existing_individual_polymer_inputs=inputs,requires_source_and_antecedent_review=True,not_accepted_into_prediction=True)]
  dest=DEST/'papers'/(cache['reference_no']+'.json');save(dest,dict(reference_no=cache['reference_no'],cache_path=item['path'],cache_sha256=item['sha256'],proposals=proposals,reference_answers_or_scores_read=False,source_pdf_or_stage0_read=False,reference_seen_previously_for_diagnosis=True,external_api_calls=0));rows.append(dict(reference_no=cache['reference_no'],path=str(dest),sha256=sha(dest),proposals=len(proposals)))
 save(DEST/'manifest.json',dict(papers=rows,papers_scanned=len(rows),generator_code_sha256=sha(__file__),reference_answers_or_scores_read=False,source_pdf_or_stage0_read=False,external_api_calls=0));print(dict(scanned=len(rows),proposed=[x['reference_no'] for x in rows if x['proposals']]))


if __name__=='__main__':main()
