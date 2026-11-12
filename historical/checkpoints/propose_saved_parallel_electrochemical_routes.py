"""Propose recovery from already-frozen prediction quotations only.

No source document, reference, score or original PDF is an input. A proposal
does not change predictions and must receive a separate source/scope review.
"""
import re
from prepare_audit import OUT,read,save,sha,canonical

DEST=OUT/'saved_parallel_electrochemical_routes_recovery'


def capture(text,pattern):
 m=re.search(pattern,text,re.S);assert m,pattern
 return {k:dict(value_raw=value,original_quote_span=list(m.span(k))) for k,value in m.groupdict().items()}


def main():
 rows=[]
 selectors={
  'precursor_workup':lambda t:t.startswith('Poly(3-methylthienyl methacrylate) (PMTM) was prepared by free-radical') and t.endswith('by repeated precipitations.'),
  'chemical_oxidation':lambda t:t.startswith('PMTM1 (78 mg) was dissolved') and t.endswith('precipitated in methanol.'),
  'dcm_galvanostatic':lambda t:t.startswith('As the second route for the oxidative polymerization of PMTM1,') and t.endswith('(GPMTM1D).'),
  'pc_galvanostatic':lambda t:t.startswith('For the self-polymerization of PMTM1,') and t.endswith('(GPMTM1P).'),
  'galvanostatic_solvents':lambda t:t=='Propylene carbonate and dichloromethane were used as the solvents for the galvanostatic polymerization of PMTM1.',
  'galvanostatic_category':lambda t:t=='Oxidative Polymerization of PMTM1 by Constant-Current Electrolysis (GPMTM1)',
  'pyrrole_graft':lambda t:t.startswith('PMTM2/PPy graft copolymers were prepared by') and 'supporting electrolyte' in t and t.endswith('reference electrode.'),
  'acn_thiophene_graft':lambda t:t.startswith('For the grafting process with thiophene,') and 'The electrolysis cell contained' in t and t.endswith('nitrogen atmosphere.'),
  'pristine_control':lambda t:t=='Under the same synthesis conditions, PPy was synthesized, and both sides of the film were examined.',
  'sem_faces_and_wash':lambda t:t.startswith('The surface morphology of the solution sides of PMTM2/PPy') and 'However, the electrode sides' in t and t.endswith('some of the irregularities were removed.')}
 for item in read(OUT/'existing_evidence_recovery_inputs/manifest.json')['papers']:
  assert sha(item['path'])==item['sha256'];cache=read(item['path']);ref=cache['reference_no'];upath=OUT/'upstream_prediction_evidence_inventory/papers'/(ref+'.json');up=read(upath)
  pool={canonical(q['text']):q for q in cache['source_quotations']+up['new_source_quotations']}
  picked={k:[q for q in pool.values() if match(q['text'])] for k,match in selectors.items()};proposals=[]
  if all(len(qs)==1 for qs in picked.values()):
   fragments={k:dict(existing_quote=qs[0],text_sha256=canonical(qs[0]['text']),captures={}) for k,qs in picked.items()}
   patterns={
    'precursor_workup':r'(?P<polymerization>free-radical polymerization).*?(?P<initiator>azobisisobutyronitrile \(AIBN\)).*?(?P<precipitate>poured into methanol).*?(?P<filter>filtered off), (?P<dry> dried in vacuo|dried in vacuo), and (?P<purification>purified by repeated precipitations)',
    'chemical_oxidation':r'(?P<input>PMTM1) \((?P<polymer_mass>78) (?P<polymer_mass_unit>mg)\) was (?P<dissolve>dissolved).*?in (?P<solvent_volume>5) (?P<solvent_volume_unit>mL) of (?P<solvent>dichloromethane).*?solution of (?P<oxidant_mass>10) (?P<oxidant_mass_unit>g).*?in (?P<oxidant_solvent_volume>15) (?P<oxidant_solvent_volume_unit>mL) of (?P<oxidant_solvent>nitromethane) was (?P<add>added dropwise).*?After a (?P<duration>24)-(?P<duration_unit>h) reaction time, the (?P<appearance>gray) product was (?P<precipitate>precipitated in methanol)',
    'dcm_galvanostatic':r'(?P<mass>50) (?P<mass_unit>mg) of (?P<input>PMTM1) was (?P<dissolve>dissolved) in (?P<solvent>dichloromethane).*?at (?P<current>50) (?P<current_unit>mA) for (?P<duration>30) (?P<duration_unit>min) at (?P<temperature_raw>.*?)under an (?P<atmosphere>inert atmosphere)\. (?P<film>Black films) were (?P<peel>peeled) from the (?P<support>anode) and (?P<dry>dried in vacuo) \((?P<product>GPMTM1D)\)',
    'pc_galvanostatic':r'(?P<electrode>platinum electrode) was (?P<coat>coated) with (?P<input>PMTM1), and (?P<electrolyze>electrolyses) were carried out in (?P<solvent>propylene carbonate) \((?P<product>GPMTM1P)\)',
    'pyrrole_graft':r'(?P<product>PMTM2/PPy graft copolymers).*?(?P<operation>electrochemical polymerization) of (?P<monomer>pyrrole) on (?P<coated_input>PMTM2-coated electrodes).*?in (?P<media>distilled water and ACN) containing (?P<monomer_concentration>0\.02) (?P<concentration_unit>mol/L) pyrrole and (?P<electrolyte_concentration>0\.05) mol/L.*?at the oxidation potential of pyrrole \((?P<potential>1\.0) (?P<potential_unit>V)\)',
    'acn_thiophene_graft':r'(?P<electrode>platinum electrode) was (?P<coat>coated) with (?P<input>PMTM2).*?contained (?P<monomer_concentration>0\.02) (?P<concentration_unit>mol/L) (?P<monomer>thiophene) and (?P<electrolyte_concentration>0\.05) mol/L (?P<electrolyte>TBAFB) in (?P<solvent>ACN).*?at (?P<potential>1\.9) (?P<potential_unit>V) for (?P<duration>60) (?P<duration_unit>min) under a (?P<atmosphere>nitrogen atmosphere)'}
   for key,pattern in patterns.items():fragments[key]['captures']=capture(fragments[key]['existing_quote']['text'],pattern)
   proposals=[dict(proposal_id='separate_precursor_to_PC_DCM_and_graft_routes',fragments=fragments,requires_independent_source_and_scope_review=True,not_accepted_into_prediction=True,proposed_change_categories=['restore_saved_operations_and_workup','repair_parallel_route_input_identity','restore_parameter_scope','preserve_SEM_faces_and_wash_states'],cannot_infer_missing_wash_duration_or_PTh_DCM_recipe_from_these_fragments=True,no_category_label_as_physical_intermediate=True,no_property_values_or_bindings_modified=True)]
  dest=DEST/'papers'/(ref+'.json');save(dest,dict(reference_no=ref,cache_path=item['path'],cache_sha256=item['sha256'],upstream_cache_path=str(upath),upstream_cache_sha256=sha(upath),proposals=proposals,reference_answers_or_scores_read=False,source_pdf_or_stage0_read=False,reference_seen_previously_for_diagnosis=True,external_api_calls=0));rows.append(dict(reference_no=ref,path=str(dest),sha256=sha(dest),proposals=len(proposals)))
 save(DEST/'manifest.json',dict(papers=rows,papers_scanned=len(rows),groups=sum(x['proposals'] for x in rows),generator_code_sha256=sha(__file__),not_accepted_into_predictions=True,reference_answers_or_scores_read=False,source_pdf_or_stage0_read=False,external_api_calls=0))
 print(dict(scanned=len(rows),proposed=[x['reference_no'] for x in rows if x['proposals']],accepted_prediction_changes=0))


if __name__=='__main__':main()
