"""Recover distinct old recipe steps with reagent-specific quantities and scope."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha

TRIAL=OUT/'process_relation_trial_023'
EXTENSION='process_saved_cyclopropane_recipes_recovery'


def build(p,approval):
 fragments=deepcopy(p['fragments']);ops=[];states=[];bindings=[];orders=[];index=[]
 for branch in ['urethane','urea','carbodiimide','amide','amine']:
  caps=fragments[branch]['captures'];anchor=p['existing_class_and_step_anchors'][branch];initial=branch.upper()+'_INITIAL';states.append(dict(id=initial,kind='state',identity=branch+' explicitly reported example',stage='before quoted preparation',state='reported reactant mixture; initial physical phase not specified' if branch=='amine' else 'reported reactants and solutions',input_materials=[caps[k]['value_raw'] for k in ['reactant1','reactant2'] if k in caps],source_fragment=branch,original_class_pointer=anchor['sample_pointer'],not_all_table_variants=True));bindings.append(dict(id='B_'+initial,kind='binding',output_state_id=initial,original_class_pointer=anchor['sample_pointer'],relation='example_belongs_to_reported_polymer_family_not_same_batch_as_all_table_rows',source_fragment=branch));last=initial;lastop=None
  def parameter(role,key,unit=None,fragment=branch,**kw):
   c=fragments[fragment]['captures'][key];v=dict(role=role,value_raw=c['value_raw'],source_fragment=fragment,source_capture=key,**kw)
   if unit:v['unit_normalized']=unit
   return v
  def quantities():
   pars=[]
   for side in ['1','2']:
    if 'reactant'+side not in caps:continue
    reagent=caps['reactant'+side]['value_raw'];stream='feed' if side=='1' else 'receiving mixture'
    for key,role,unit in [('mass','reagent mass','g'),('moles','reagent amount','mol')]:
     if key+side in caps:pars.append(parameter(role,key+side,unit,substance_raw=reagent,stream=stream))
    if 'solvent'+side in caps:pars.append(parameter('solvent','solvent'+side,stream=stream))
    if 'volume'+side in caps:pars.append(parameter('solvent volume','volume'+side,'mL',substance_raw=caps['solvent'+side]['value_raw'],stream=stream))
   if 'atmosphere' in caps:pars.append(parameter('atmosphere','atmosphere'))
   if 'temperature' in caps:pars.append(parameter('reaction or addition temperature','temperature','°C'))
   if 'temperature_description' in caps:pars.append(parameter('receiving solution temperature description','temperature_description'))
   return pars
  def emit(label,name,text,pars,fragment=branch,**kw):
   nonlocal last,lastop
   oid=branch.upper()+'_'+label;sid=oid+'_STATE';opix=len(ops);six=len(states);ops.append(dict(id=oid,kind='operation',name=name,scope=branch+' explicitly reported example',input_state_id=last,output_state_id=sid,parameters=pars,source_fragment=fragment,**kw));states.append(dict(id=sid,kind='state',identity=branch+' explicitly reported example',stage='after '+name,state=text,operation_id=oid,source_fragment=fragment));bindings.append(dict(id='B_'+oid,kind='binding',input_state_id=last,output_state_id=sid,operation_id=oid,relation='within_this_quoted_example_preparation',source_fragment=fragment));
   if lastop:orders.append(dict(id='ORDER_'+oid,kind='order',before_operation_id=lastop,after_operation_id=oid,scope=branch+' explicitly reported example',source_fragment=fragment))
   index.append(dict(branch=branch,step=label,operation_index=opix,state_index=six));last=sid;lastop=oid
  if branch in ['urethane','urea','amide']:
   pars=quantities()
   if branch=='urea':pars.append(parameter('dropwise addition duration','addition_duration','min'))
   if branch=='amide':
    for key,role,unit,substance in [('base_mass','base mass','g','base'),('base_moles','base amount','mol','base'),('surfactant_mass','surfactant mass','g','surfactant')]:pars.append(parameter(role,key,unit,substance_raw=caps[substance]['value_raw']))
    pars.append(parameter('stirring','stirring'))
   emit('ADD','add reported reactant solution','reaction mixture after reported addition',pars)
   if branch in ['urethane','amide']:
    time,=[r for r in p['existing_reaction_times'] if r['branch']==branch];emit('REACTION','continue reported polymerization','reaction mixture after native reported reaction interval',[dict(role='native reported reaction duration',value_raw=time['value_raw'],source_native_parameter_pointer=time['pointer'],source_native_parameter_sha256=time['value_sha256'])],reflux_or_cooling_not_added_from_new_source=True)
   if branch=='urethane':
    emit('ETHANOL','treat prepared polyurethane with boiling ethanol','ethanol-treated polyurethane',[parameter('treatment medium','treat_medium',fragment='urethane_workup')],fragment='urethane_workup')
    emit('DRY','dry ethanol-treated polyurethane','dried polyurethane',[],fragment='urethane_workup',drying_temperature_time_and_atmosphere_unknown=True)
    emit('REDISSOLVE','redissolve polyurethane for reprecipitation','polyurethane solution for reprecipitation',[parameter('redissolution solvent','solvent',fragment='urethane_workup')],fragment='urethane_workup')
    emit('PRECIPITATE','reprecipitate polyurethane','reprecipitated polyurethane',[parameter('precipitant','precipitant',fragment='urethane_workup')],fragment='urethane_workup')
  elif branch=='carbodiimide':
   pars=quantities()+[parameter('catalyst amount','catalyst_drops','drops',substance_raw=caps['catalyst']['value_raw'])];emit('SOLUTION','prepare reported catalysed solution','diisocyanate solution containing reported catalyst',pars)
   emit('STAND','allow reaction solution to stand','solution after room-temperature interval',[parameter('standing temperature description','stand_temperature'),parameter('standing duration','stand_duration','min')])
   emit('BOIL','boil reaction solution','reaction mixture after reported boiling interval',[parameter('boiling duration','boil_duration','h')],numerical_boiling_temperature_not_inferred=True)
  else:
   pars=quantities()+[parameter('additive qualitative amount','additive_amount',substance_raw=caps['additive']['value_raw'])];emit('HEAT','heat reported monomer mixture','heated reaction mixture',pars,masses_retained_as_printed_not_corrected_by_calculation=True,heating_duration_and_later_workup_not_added=True)
 return dict(operations=ops,states=states,bindings=bindings,orders=orders,parameters=[],step_index=index,saved_fragments=fragments,existing_class_and_step_anchors=deepcopy(p['existing_class_and_step_anchors']),existing_reaction_times=deepcopy(p['existing_reaction_times']),missing_experimental_tails_not_recovered=True,source_approval_path=approval['path'],source_approval_sha256=approval['sha256'],original_property_values_and_bindings_unchanged=True,new_pdf_information_extracted=0)


def main():
 parentpath=OUT/'process_relation_trial_022/freeze.json';parent=read(parentpath);approval,=read(OUT/'saved_cyclopropane_recipes_recovery/source_reviews/manifest.json')['papers'];assert sha(approval['path'])==approval['sha256'];review=read(approval['path']);assert sha(review['proposal_path'])==review['proposal_sha256'];packet=read(review['proposal_path']);rows=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no']==approval['reference_no']:
   new=read(p['candidate_path']);assert EXTENSION not in new;new[EXTENSION]=[build(packet['proposals'][0],approval)];dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new);row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  rows.append(row)
 save(TRIAL/'freeze.json',dict(version=TRIAL.name,parent_trial='process_relation_trial_022',parent_trial_freeze_sha256=sha(parentpath),baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),proposal_generation_code_sha256=sha(OUT/'propose_saved_cyclopropane_recipes.py'),papers=rows,papers_total=101,changed_papers_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows),property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,stable_workflow_release=False,external_api_calls=0));print(dict(papers=101,changed_this_round=1,cumulative_changed_papers=sum(bool(x.get('changed_from_parent')) for x in rows)))


if __name__=='__main__':main()
