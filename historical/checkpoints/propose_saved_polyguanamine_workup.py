"""Proposal inputs are frozen predictions/quotes only, never evaluation items."""
import re
from prepare_audit import OUT,read,save,sha

DEST=OUT/'saved_polyguanamine_workup_recovery'
NUM=r'\d+(?:\.\d+)?'
PATS={
 'charge':re.compile(r'(?P<monomer_label>\w+) \((?P<monomer_mass>'+NUM+r') (?P<monomer_mass_unit>g), (?P<monomer_amount>'+NUM+r') (?P<monomer_amount_unit>mmol)\) was (?P<charge_action>added) to (?P<first_solvent>dimethyl sulfoxide \(DMSO\)) \((?P<first_solvent_volume>'+NUM+r') (?P<first_solvent_volume_unit>ml)\) in the presence of (?P<base>sodium hydride) \((?P<base_mass>'+NUM+r') (?P<base_mass_unit>g), (?P<base_amount>'+NUM+r') (?P<base_amount_unit>mmol)\) with (?P<mixing>stirring), and then (?P<second_solvent>dimethyl acetamide \(DMA\)) solution \((?P<second_solvent_volume>'+NUM+r') (?P<second_solvent_volume_unit>ml)\) of (?P<second_monomer>[0-9,a-z-]+) \((?P<second_monomer_mass>'+NUM+r') (?P<second_monomer_mass_unit>g), (?P<second_monomer_amount>'+NUM+r') (?P<second_monomer_amount_unit>mmol)\) was (?P<addition>added dropwise) at (?P<addition_temperature>'+NUM+r')(?P<addition_temperature_unit>°C)\. The reaction mixture was (?P<reaction_action>stirred) at (?P<reaction_temperature>room temperature) for (?P<reaction_duration>'+NUM+r') (?P<reaction_duration_unit>h), and was (?P<precipitation_action>poured) into (?P<first_precipitant>excess methanol)\.'),
 'separation':re.compile(r'Then, the product was (?P<dissolution>dissolved) in (?P<dissolution_solvent>tetrahydrofuran \(THF\)) for reprecipitation, and a (?P<impurity_quantity_qualifier>small amount) of (?P<impurity_state>insoluble compound in THF) \((?P<impurity_label>\w+)\) was (?P<impurity_collection>filtered off) \((?P<impurity_mass>'+NUM+r') (?P<impurity_mass_unit>g), (?P<impurity_yield>'+NUM+r')(?P<impurity_yield_unit>%)\)\. The (?P<retained_stream>filtrate) was (?P<reprecipitation>poured) into (?P<reprecipitant>methanol) to give (?P<product_family>polyguanamine)\.'),
 'drying':re.compile(r'The (?P<isolated_state>isolated polyguanamine) (?P<product_label>\w+) was (?P<drying>dried) (?P<drying_environment>in vacuo) to give a yield of (?P<product_mass>'+NUM+r') (?P<product_mass_unit>g) \((?P<product_yield>'+NUM+r')(?P<product_yield_unit>%)\)\.'),
 'old_wash_state':re.compile(r'The reaction mixture was stirred at (?P<wash_previous_temperature>room temperature) for (?P<wash_previous_duration>'+NUM+r') h, and was poured into excess methanol\. The (?P<first_precipitate>precipitate) was (?P<first_collection>collected by filtration) and (?P<washing>washed) with (?P<wash_liquid>methanol)\.')}


def main():
 rows=[]
 for p in read(OUT/'existing_evidence_recovery_inputs/manifest.json')['papers']:
  assert sha(p['path'])==p['sha256'];cache=read(p['path']);path=OUT/'candidate_v10'/(p['reference_no']+'.json');pred=read(path);ns='native_process_context' if 'native_process_context' in pred else 'native_process_supplement';native=pred.get(ns,{});found={};proposals=[]
  for name in ['charge','separation','drying']:
   qs=[]
   for q in cache['source_quotations']:
    m=PATS[name].fullmatch(q['text'])
    if m:qs.append((q,m))
   if len(qs)!=1:break
   q,m=qs[0];found[name]=dict(existing_quote=q,captures={k:dict(value_raw=v,original_quote_span=list(m.span(k))) for k,v in m.groupdict().items()})
  if len(found)==3:
   sample_matches=[(i,s,PATS['old_wash_state'].fullmatch(s.get('state_description',''))) for i,s in enumerate(native.get('samples',[])) if PATS['old_wash_state'].fullmatch(s.get('state_description',''))]
   label=found['drying']['captures']['product_label']['value_raw'];byproduct=found['separation']['captures']['impurity_label']['value_raw']
   targets=[dict(path=f'/{ns}/samples/{i}',sample_id=s['sample_id'],original_sample=s) for i,s in enumerate(native['samples']) if s.get('sample_label_raw')==label]
   impurities=[dict(path=f'/{ns}/samples/{i}',sample_id=s['sample_id'],original_sample=s) for i,s in enumerate(native['samples']) if s.get('sample_label_raw')==byproduct and 'insoluble' in s.get('state_description','')]
   if len(sample_matches)==len(targets)==len(impurities)==1:
    i,s,m=sample_matches[0];found['old_wash_state']=dict(existing_assertion=dict(path=f'/{ns}/samples/{i}/state_description',value_sha256=None,text=s['state_description']),captures={k:dict(value_raw=v,original_quote_span=list(m.span(k))) for k,v in m.groupdict().items()})
    if found['charge']['captures']['reaction_duration']['value_raw']==found['old_wash_state']['captures']['wash_previous_duration']['value_raw']:
     locators=[{(o['source_path'],o['original_evidence_metadata'].get('block_id')) for o in f['existing_quote']['occurrences']} for name,f in found.items() if name!='old_wash_state'];common=set.intersection(*locators)
     if common:proposals.append(dict(proposal_id='explicit_typical_polyguanamine_workup',fragments=found,product_target=targets[0],impurity_target=impurities[0],old_wash_state_target=dict(path=f'/{ns}/samples/{i}',sample_id=s['sample_id']),shared_saved_source_locators=[dict(source_path=p,block_id=b) for p,b in sorted(common)],scope_requires_separate_source_review=True,catalytic_use_and_other_polymer_workups_not_recovered=True,total_crude_yield_not_recovered=True))
  dest=DEST/'papers'/(p['reference_no']+'.json');save(dest,dict(reference_no=p['reference_no'],cache_path=p['path'],cache_sha256=p['sha256'],candidate_source=dict(path=str(path),sha256=sha(path)),proposals=proposals,accepted_into_prediction=False,reference_files_or_scores_used_as_generator_inputs=False,reference_seen_previously_during_error_diagnosis=True,pdf_or_stage0_source_read_by_generator=False,property_outputs_modified=False,external_api_calls=0));rows.append(dict(reference_no=p['reference_no'],path=str(dest),sha256=sha(dest),proposals=len(proposals)))
 result=dict(papers=rows,papers_scanned=len(rows),groups=sum(x['proposals'] for x in rows),generator_code_sha256=sha(__file__),reference_files_or_scores_used_as_generator_inputs=False,reference_seen_previously_during_error_diagnosis=True,pdf_or_stage0_source_read_by_generator=False,external_api_calls=0);save(DEST/'manifest.json',result);print({'papers':len(rows),'groups':result['groups'],'proposed_papers':[x['reference_no'] for x in rows if x['proposals']]})

if __name__=='__main__':main()
