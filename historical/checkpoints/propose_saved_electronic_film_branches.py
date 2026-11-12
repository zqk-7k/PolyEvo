"""Identify source-labelled film variants using frozen prediction quotations only."""
import re
from prepare_audit import OUT,read,save,sha

DEST=OUT/'saved_electronic_film_branches_recovery'
PATS={
 'fraction_scope':re.compile(r'The polymer thin films of\s*the (?P<fraction>DCE fractions) of both (?P<number_a>\d+), \((?P<formula_a>S+N)\) , and (?P<number_b>\d+), \((?P<formula_b>S+N)\) , were prepared by both (?P<casting>casting) and (?P<spin>spin-coating) techniques\.'),
 'sem_caption':re.compile(r'Figure (?P<figure>\d+)\. SEM micrographs of .*?thin films deposited on an (?P<substrate>ITO glass) substrate by casting and spincoating: \(a\) \((?P<formula_a>S+N)\)(?:<sub>x</sub>)? (?P<mode_a>cast) film; \(b\) \((?P<formula_b>S+N)\)(?:<sub>x</sub>)? (?P<mode_b>spin-coated) film; \(c\) \((?P<formula_c>S+N)\)(?:<sub>x</sub>)? (?P<mode_c>cast) film; \(d\) \((?P<formula_d>S+N)\)(?:<sub>x</sub>)? (?P<mode_d>spin-coated) film\.'),
 'sem_method':re.compile(r'For (?P<purpose>scanning electron microscopy \(SEM\)) studies, thin films were prepared by both the (?P<cast>casting) and the (?P<spin>spin-coating) method\. (?P<substrate>Indium tin oxide \(ITO\) conducting glass) was used as the substrate in both cases\.'),
 'ups_method':re.compile(r'For the (?P<purpose>ultraviolet photoelectron spectroscopy \(UPS\)) study, thin films of \((?P<formula_a>S+N)\)<sub>x</sub> or \((?P<formula_b>S+N)\)<sub>x</sub> were prepared on a (?P<substrate>gold-coated glass substrate) at (?P<temperature>room temperature) in (?P<atmosphere>air) by (?P<deposition_description>either the casting or the spin-coating method, respectively)\.'),
 'ups_results':re.compile(r'UPS spectra are shown in Figures (?P<figure_a>\d+) and (?P<figure_b>\d+) for (?P<method>solution-cast) films of (?P<number_a>\d+) and (?P<number_b>\d+), respectively\.'),
 'doping_temperature':re.compile(r'Iodine doping was carried out at (?P<temperature>room temperature)')}
BODY_PATS={
 'materials':re.compile(r'In a further study of their electronic properties, thin films of both polymers (?P<number_a>\d+),.*? and (?P<number_b>\d+),.*?were obtained',re.S),
 'morphology':re.compile(r'Films prepared by the (?P<spin_method>spin-coating) method did not present any apparent irregularities and their surfaces were (?P<spin_surface>quite smooth), whereas films obtained by the (?P<cast_method>casting) route presented a (?P<cast_surface>rough surface)\. From the SEM morphology, it is obvious that the spincoating method gave better quality films with a (?P<spin_comparison>much more homogeneous surface), as compared to the casting method\.'),
 'neutral_state':re.compile(r'both polymers in the (?P<state>neutral undoped state) \((?P<color>dark red) in color\)'),
 'dopant':re.compile(r'doped with (?P<dopant>iodine)'),
 'window':re.compile(r'grew rapidly in the (?P<window_qualifier>first) (?P<window_duration>\d+) (?P<window_duration_unit>min)'),
 'doped_color':re.compile(r'During doping, the color of the films changed from (?P<input_color_group>brown or yellow-brown) to (?P<output_color>almost black)\.'),
 'air':re.compile(r'(?P<air_action>Exposing) the thin films to (?P<air_medium>air) resulted in a (?P<conductivity_change>decrease in the conductivities) of the mixed polymers\. After (?P<air_duration>\d+) (?P<air_duration_unit>h), the conductivity values (?P<after_change>dropped)')}


def pack(q,m):return dict(existing_quote=q,captures={k:dict(value_raw=v,original_quote_span=list(m.span(k))) for k,v in m.groupdict().items()})


def main():
 rows=[]
 for p in read(OUT/'existing_evidence_recovery_inputs/manifest.json')['papers']:
  assert sha(p['path'])==p['sha256'];cache=read(p['path']);path=OUT/'candidate_v10'/(p['reference_no']+'.json');pred=read(path);origin=pred['property_source'];assert sha(origin['path'])==origin['sha256'];original=read(origin['path']);ns='native_process_context' if 'native_process_context' in pred else 'native_process_supplement';samples=pred.get(ns,{}).get('samples',[]);frags={};proposals=[]
  for name,pat in PATS.items():
   candidates=[(q,m) for q in cache['source_quotations'] if (m:=pat.fullmatch(q['text']))]
   if len(candidates)!=1:break
   q,m=candidates[0];frags[name]=pack(q,m)
  bodies=[]
  for q in cache['source_quotations']:
   ms={k:pat.search(q['text']) for k,pat in BODY_PATS.items()}
   if all(ms.values()):
    names=[k for m in ms.values() for k in m.groupdict()];assert len(names)==len(set(names))
    bodies.append(dict(existing_quote=q,captures={k:dict(value_raw=v,original_quote_span=list(m.span(k)),pattern_group=group) for group,m in ms.items() for k,v in m.groupdict().items()}))
  if len(frags)==6 and len(bodies)==1:
   frags['body']=bodies[0];v=lambda g,k:frags[g]['captures'][k]['value_raw'];products=[]
   for slot in ['a','b']:
    number=v('fraction_scope','number_'+slot);formula=v('fraction_scope','formula_'+slot);ss=[(i,s) for i,s in enumerate(samples) if s.get('sample_label_raw')=='polymer '+number and s.get('sample_kind')=='synthesis_batch']
    if len(ss)!=1:break
    i,s=ss[0];dce=[dict(path=f'/{ns}/samples/{j}',sample_id=x['sample_id'],original_sample=x) for j,x in enumerate(samples) if x.get('refers_to_entity')==s.get('refers_to_entity') and x.get('state_description','').strip().lower()=='dce fraction']
    if len(dce)!=1:break
    products.append(dict(number=number,formula=formula,material_target=dict(path=f'/{ns}/samples/{i}',sample_id=s['sample_id'],original_sample=s),fraction_target=dce[0]))
   if len(products)==2 and products[0]['formula']!=products[1]['formula'] and all(v('body','number_'+x)==v('fraction_scope','number_'+x)==v('ups_results','number_'+x) for x in ['a','b']):
    a,b=(x['formula'] for x in products)
    if [v('sem_caption','formula_'+x) for x in ['a','b','c','d']]==[a,a,b,b] and [v('ups_method','formula_'+x) for x in ['a','b']]==[a,b]:
     prior=[]
     for i,s in enumerate(original.get('property_series',[])):
      if s.get('property_name_raw')=='iodine_doping_duration':
       for j,x in enumerate(s['points']):
        if x.get('value_raw')==v('body','window_duration') and x.get('unit_raw','').startswith(v('body','window_duration_unit')):prior.append(dict(path=f'/property_series/{i}/points/{j}',original_point=x,source_role_unqualified=True))
     proposals=[dict(proposal_id='source_labelled_SEM_UPS_and_doped_film_histories',fragments=frags,products=products,existing_unqualified_doping_interval_points=prior,SEM_and_UPS_and_conductivity_specimens_not_physically_equated=True,UPS_reported_deposition_wordings_preserved_separately=True,initial_color_assignment_to_individual_polymers_not_recovered=True,conductivity_values_not_reextracted_or_repaired_from_OCR=True)]
  dest=DEST/'papers'/(p['reference_no']+'.json');save(dest,dict(reference_no=p['reference_no'],cache_path=p['path'],cache_sha256=p['sha256'],candidate_source=dict(path=str(path),sha256=sha(path)),property_source=origin,proposals=proposals,accepted_into_prediction=False,reference_files_or_scores_used_as_generator_inputs=False,reference_seen_previously_during_error_diagnosis=True,pdf_or_stage0_source_read_by_generator=False,property_outputs_modified=False,external_api_calls=0));rows.append(dict(reference_no=p['reference_no'],path=str(dest),sha256=sha(dest),proposals=len(proposals)))
 result=dict(papers=rows,papers_scanned=len(rows),groups=sum(p['proposals'] for p in rows),generator_code_sha256=sha(__file__),reference_files_or_scores_used_as_generator_inputs=False,reference_seen_previously_during_error_diagnosis=True,pdf_or_stage0_source_read_by_generator=False,external_api_calls=0);save(DEST/'manifest.json',result);print({'papers':len(rows),'groups':result['groups'],'proposed_papers':[x['reference_no'] for x in rows if x['proposals']]})

if __name__=='__main__':main()
