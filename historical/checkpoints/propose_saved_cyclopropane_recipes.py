"""Split stored recipe openings; never read reference/source/score files."""
from prepare_audit import OUT,read,save,sha,canonical
from propose_saved_parallel_electrochemical_routes import capture

DEST=OUT/'saved_cyclopropane_recipes_recovery'
PATTERNS={
 'urethane':r'Under (?P<atmosphere>nitrogen) atmosphere a solution of (?P<mass1>[\d.]+) g\. \((?P<moles1>[\d.]+) mole\) of (?P<reactant1>.*?) in (?P<volume1>[\d.]+) ml\. of (?P<solvent1>.*?) was (?P<addition>added with stirring) to a (?P<temperature_description>boiling) solution of (?P<mass2>[\d.]+) g\. \((?P<moles2>[\d.]+) mole\) of (?P<reactant2>.*?) in (?P<volume2>[\d.]+) ml\. of (?P<solvent2>.*?)\.',
 'urea':r'During (?P<addition_duration>[\d.]+) min\. a solution of (?P<mass1>[\d.]+) g\. \((?P<moles1>[\d.]+) mole\) of (?P<reactant1>.*?) in (?P<volume1>[\d.]+) ml\. of (?P<solvent1>.*?) was (?P<addition>added dropwise) at (?P<temperature>[\d.]+)°C\. under (?P<atmosphere>nitrogen) atmosphere to a solution of (?P<mass2>[\d.]+) g\. \((?P<moles2>[\d.]+) mole\) of (?P<reactant2>.*?) in (?P<volume2>[\d.]+) ml\. of (?P<solvent2>.*?)\.',
 'carbodiimide':r'A solution of (?P<mass1>[\d.]+) g\. of (?P<reactant1>.*?) in (?P<volume1>[\d.]+) ml\. of (?P<solvent1>dry benzene) containing (?P<catalyst_drops>\d+) drops of (?P<catalyst>.*?) as catalyst was (?P<stand>allowed to stand) at (?P<stand_temperature>room temperature) for (?P<stand_duration>\d+) min\., and (?P<boil>boiled) during (?P<boil_duration>\d+) hrs\.',
 'amide':r'Under (?P<stirring>vigorous stirring), a solution of (?P<mass1>[\d.]+) g\. \((?P<moles1>[\d.]+) mole\) of (?P<reactant1>.*?) in (?P<solvent1>benzene) was (?P<addition>added) to an (?P<temperature_description>ice cooled) solution of (?P<mass2>[\d.]+) g\. \((?P<moles2>[\d.]+) mole\) of (?P<reactant2>.*?), (?P<base_mass>[\d.]+) g\. \((?P<base_moles>[\d.]+) mole\) of (?P<base>sodium hydroxide) and (?P<surfactant_mass>[\d.]+) g\. of (?P<surfactant>sodium lauryl sulfate) in (?P<volume2>[\d.]+) ml\. of (?P<solvent2>water)\.',
 'amine':r'A mixture of (?P<mass1>[\d.]+) g\. \((?P<moles1>[\d.]+) mole\) of (?P<reactant1>.*?), (?P<mass2>[\d.]+) g\. \((?P<moles2>[\d.]+) mole\) of (?P<reactant2>.*?) and a (?P<additive_amount>small amount) of (?P<additive>ammonium chloride) was (?P<heat>heated) at (?P<temperature>[\d.]+)°C\. under (?P<atmosphere>nitrogen) atmosphere\.',
 'urethane_workup':r'The (?P<product>polyurethane) prepared was (?P<treat>treated) with (?P<treat_medium>boiling ethanol), (?P<dry>dried) and (?P<purify>purified by reprecipitation) using (?P<solvent>DMF) as solvent and (?P<precipitant>methanol) as precipitant\.'}


def main():
 manifest=[]
 definitions=dict(urethane=lambda t:t.startswith('Under nitrogen atmosphere a solution of 0.977 g.'),urea=lambda t:t.startswith('1) During 30 min. a solution'),carbodiimide=lambda t:t.startswith('3) A solution of 2.9 g.'),amide=lambda t:t.startswith('Under vigorous stirring, a solution of 2.606 g.'),amine=lambda t:t.startswith('A mixture of 4.827 g.'),urethane_workup=lambda t:t.startswith('The polyurethane prepared was treated with boiling ethanol'))
 for item in read(OUT/'existing_evidence_recovery_inputs/manifest.json')['papers']:
  assert sha(item['path'])==item['sha256'];cache=read(item['path']);picked={k:[q for q in cache['source_quotations'] if match(q['text'])] for k,match in definitions.items()};proposals=[]
  if all(len(q)==1 for q in picked.values()):
   pred=read(OUT/'candidate_v10'/(cache['reference_no']+'.json'));ctx=pred['native_process_context'];fragments={k:dict(existing_quote=qs[0],text_sha256=canonical(qs[0]['text']),captures=capture(qs[0]['text'],PATTERNS[k])) for k,qs in picked.items()};anchors={}
   for name,step_id in [('urethane','ps001'),('urea','ps002'),('carbodiimide','ps003'),('amide','ps004'),('amine','ps005')]:
    i,step=next((i,s) for i,s in enumerate(ctx['process_steps']) if s['step_id']==step_id);sid,=step['output_sample_ids'];j,sample=next((j,s) for j,s in enumerate(ctx['samples']) if s['sample_id']==sid);anchors[name]=dict(step_pointer='/native_process_context/process_steps/'+str(i),step_sha256=canonical(step),sample_pointer='/native_process_context/samples/'+str(j),sample_sha256=canonical(sample),family=sample['polymer_name'])
   saved_times=[]
   for name in ['urethane','amide']:
    a=anchors[name];step=ctx['process_steps'][int(a['step_pointer'].rsplit('/',1)[1])];saved_times.append(dict(branch=name,pointer=a['step_pointer']+'/parameters/reaction_time',value_raw=step['parameters']['reaction_time'],value_sha256=canonical(step['parameters']['reaction_time'])))
   proposals=[dict(proposal_id='separate_five_cyclopropane_examples',fragments=fragments,existing_class_and_step_anchors=anchors,existing_reaction_times=saved_times,full_table_variants_not_assigned_example_recipe=True,missing_experimental_tails_not_recovered=True,source_printed_mass_not_corrected_by_stoichiometric_calculation=True,requires_source_review=True,not_accepted_into_prediction=True)]
  dest=DEST/'papers'/(cache['reference_no']+'.json');save(dest,dict(reference_no=cache['reference_no'],cache_path=item['path'],cache_sha256=item['sha256'],proposals=proposals,reference_answers_or_scores_read=False,source_pdf_or_stage0_read=False,reference_seen_previously_for_diagnosis=True,external_api_calls=0));manifest.append(dict(reference_no=cache['reference_no'],path=str(dest),sha256=sha(dest),proposals=len(proposals)))
 save(DEST/'manifest.json',dict(papers=manifest,papers_scanned=len(manifest),generator_code_sha256=sha(__file__),reference_answers_or_scores_read=False,source_pdf_or_stage0_read=False,external_api_calls=0));print(dict(scanned=len(manifest),proposed=[x['reference_no'] for x in manifest if x['proposals']]))


if __name__=='__main__':main()
