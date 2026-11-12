"""Recover a saved LCST method only; no references, sources or scores read."""
from prepare_audit import OUT,read,save,sha,canonical
from propose_saved_parallel_electrochemical_routes import capture

DEST=OUT/'saved_cloudpoint_history_recovery'


def main():
 rows=[]
 for item in read(OUT/'existing_evidence_recovery_inputs/manifest.json')['papers']:
  assert sha(item['path'])==item['sha256'];cache=read(item['path'])
  # The short quotation is a frozen property evidence field, not a newly
  # parsed source paragraph. A source review is required before application.
  qs=[q for q in cache['source_quotations'] if q['text'].startswith('LCST Measurements. Polymers are first dissolved') and q['text'].endswith('from clear to turbid was recorded.')]
  proposals=[]
  if len(qs)==1:
   q=qs[0];caps=capture(q['text'],r'(?P<medium>deionized water).*?(?P<dilution>diluted to different concentrations).*?(?P<heating>heated slowly in an oil bath).*?(?P<transition>change from clear to turbid)')
   proposals=[dict(proposal_id='saved_slow_oil_bath_cloud_transition',fragments=dict(lcst_method=dict(existing_quote=q,text_sha256=canonical(q['text']),captures=caps)),only_existing_individual_LCST_diluted_states_are_eligible=True,conditional_method_applications_are_ineligible=True,no_cloudpoint_values_or_concentrations_to_be_added=True,requires_source_and_scope_review=True,not_accepted_into_prediction=True)]
  dest=DEST/'papers'/(cache['reference_no']+'.json');save(dest,dict(reference_no=cache['reference_no'],cache_path=item['path'],cache_sha256=item['sha256'],proposals=proposals,source_pdf_or_stage0_read=False,reference_answers_or_scores_read=False,reference_seen_previously_for_diagnosis=True,external_api_calls=0));rows.append(dict(reference_no=cache['reference_no'],path=str(dest),sha256=sha(dest),proposals=len(proposals)))
 save(DEST/'manifest.json',dict(papers=rows,papers_scanned=len(rows),groups=sum(x['proposals'] for x in rows),generator_code_sha256=sha(__file__),reference_answers_or_scores_read=False,source_pdf_or_stage0_read=False,external_api_calls=0));print(dict(scanned=len(rows),proposed=[x['reference_no'] for x in rows if x['proposals']]))


if __name__=='__main__':main()
