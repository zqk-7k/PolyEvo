"""Recover explicit DSC thermal histories from frozen upstream quotations only."""
import re
from prepare_audit import OUT,read,save,sha

DEST=OUT/'saved_polyimide_dsc_history_recovery'
TEMP=r'\$?(?P<{name}>\d+(?:\.\d+)?)\^\{{\\circ\}}C\$?'
def temp(name):return r'\$?(?P<'+name+r'>\d+(?:\.\d+)?)\^\{\\circ\}C\$?'
PATTERNS={
 'controls':re.compile(r'The (?P<control_a>[A-Za-z0-9,/\'-]+) and the (?P<control_b>[A-Za-z0-9,/\'-]+) polyimides showed no.*?These films were (?P<control_action>annealed) at\s+'+temp('control_temperature')+r'\s+for (?P<control_minimum>\d+)–(?P<control_maximum>\d+) (?P<control_time_unit>h), (?P<control_cooling>allowed to cool slowly), and the (?P<control_rerun>DSC rerun), but again no',re.S),
 'initial':re.compile(r'DSC curves of the (?P<main_label>[A-Za-z0-9,/\'-]+) polyimide are shown in Figure 1\. Run 1 is a sample of the film which was (?P<initial_action>dried) (?P<initial_duration>\d+) (?P<initial_time_unit>h) at\s+'+temp('initial_temperature')+r'\s+on (?P<substrate>plate glass) in (?P<initial_atmosphere>air)\.'),
 'quench':re.compile(r'showed it to be (?P<initial_state>semicrystalline)\. The DSC sample of run 1 was (?P<quench_action>quenched) after (?P<heating_action>heating) to\s+'+temp('quench_temperature')+r'\s+in (?P<quench_heating_atmosphere>air) and (?P<second_run>rerun as run 2)\.'),
 'slow_cooling':re.compile(r'(?P<second_response>very weak endotherm).*?Upon (?P<second_cooling>cooling the sample of run 2 slowly) and (?P<third_run>rerunning),.*?followed by a (?P<third_response>mild endotherm)',re.S),
 'annealing':re.compile(r'The sample from run 3 was (?P<anneal_action>held) at\s+'+temp('anneal_temperature')+r'\s+in (?P<anneal_atmosphere>air) for (?P<anneal_duration>\d+) (?P<anneal_time_unit>min), (?P<third_cooling>slowly cooled) and (?P<fourth_run>subsequently rerun)\. Run 4 shows.*?and (?P<fourth_response>multiple endotherms)',re.S),
 'phase_qualification':re.compile(r'could be converted (?P<amorphous_qualifier>predominantly) to its (?P<amorphous_form>amorphous form) and subsequently (?P<recovery_interpretation>thermally annealed to induce crystallinity)')}


def main():
 rows=[]
 for p in read(OUT/'upstream_prediction_evidence_inventory/manifest.json')['papers']:
  assert sha(p['path'])==p['sha256'];packet=read(p['path']);predpath=OUT/'candidate_v10'/(p['reference_no']+'.json');pred=read(predpath);ns='native_process_context' if 'native_process_context' in pred else 'native_process_supplement';samples=pred.get(ns,{}).get('samples',[]);proposals=[]
  for q in packet['new_source_quotations']:
   matches={k:pattern.search(q['text']) for k,pattern in PATTERNS.items()}
   if not all(matches.values()):continue
   name=matches['initial']['main_label'];main_targets=[dict(path=f'/{ns}/samples/{i}',sample_id=s['sample_id'],entity_id=s.get('refers_to_entity'),original_sample=s) for i,s in enumerate(samples) if name in s.get('polymer_name','') and s.get('sample_kind')=='test_specimen' and 'for DSC' in s.get('state_description','')]
   if len(main_targets)!=1:continue
   controls=[]
   for key in ['control_a','control_b']:
    label=matches['controls'][key];choices=[dict(path=f'/{ns}/samples/{i}',sample_id=s['sample_id'],entity_id=s.get('refers_to_entity'),label=label,original_sample=s) for i,s in enumerate(samples) if label in s.get('polymer_name','') and s.get('sample_kind')=='synthesis_batch']
    if len(choices)!=1:break
    controls+=choices
   if len(controls)!=2:continue
   proposals.append(dict(proposal_id='explicit_source_DSC_rerun_histories',saved_quote=q,captures={k:dict(value_raw=v,original_quote_span=list(m.span(k)),pattern_group=group) for group,m in matches.items() for k,v in m.groupdict().items()},main_DSC_target=main_targets[0],control_material_targets=controls,
    mechanical_quenched_test_specimens_not_used=True,quench_medium_heating_rates_and_unreported_scan_endpoints_not_recovered=True,absence_of_melting_not_equated_to_fully_amorphous=True))
  dest=DEST/'papers'/(p['reference_no']+'.json');save(dest,dict(reference_no=p['reference_no'],candidate_source=dict(path=str(predpath),sha256=sha(predpath)),upstream_quote_packet=dict(path=p['path'],sha256=p['sha256']),proposals=proposals,accepted_into_prediction=False,reference_answers_or_scores_read=False,pdf_or_stage0_source_read=False,property_outputs_modified=False,external_api_calls=0));rows.append(dict(reference_no=p['reference_no'],path=str(dest),sha256=sha(dest),proposals=len(proposals)))
 result=dict(papers=rows,papers_scanned=len(rows),groups=sum(x['proposals'] for x in rows),generator_code_sha256=sha(__file__),reference_answers_or_scores_read=False,pdf_or_stage0_source_read=False,external_api_calls=0);save(DEST/'manifest.json',result);print({'scanned':len(rows),'groups':result['groups'],'papers_with_proposals':[x['reference_no'] for x in rows if x['proposals']]})

if __name__=='__main__':main()
