from copy import deepcopy
from prepare_audit import OUT,read,save,sha

TRIAL=OUT/'process_relation_trial_012'
EXTENSION='process_saved_sulfide_ether_methods_recovery'


def build(r,a):
 f=r['fragments'];v=lambda g,k:f[g]['captures'][k]['value_raw'];materials=[];states=[];ops=[];orders=[];bindings=[]
 def par(role,g,k,unit=None):return dict(role=role,value_raw=v(g,k),unit_raw=v(g,unit) if unit else None,source_fragment=g,source_capture=k)
 def temperature(g):return dict(role='temperature',value_raw=v(g,'temperature'),unit_raw='°C',source_fragment=g,source_capture='temperature',unit_basis='explicit degree marker and C in the same saved quotation')
 def op(i,label,name,ins,outs,params):
  ops.append(dict(id=i,kind='operation',sample=label,name=name,inputs=ins,outputs=outs,parameters=params));bindings.append(dict(id='SCOPE_'+i,kind='binding',sample=label,operation_id=i,input_nodes=ins,output_states=outs,scope='each named source material is an independent method instance; not a pooled composition'))
 methyl=v('methyl','material');materials.append(dict(id='METHYL_FEED',kind='material_identity_annotation',name=methyl,physical_state_not_reported=True));states.append(dict(id='METHYL_SOLID',kind='state',sample='source polymer derived from '+methyl,state=v('methyl','output_state'),history='after the reported slow polymerization under fluorescent light',AIBN_60C_route_not_assigned=True))
 op('METHYL_POLYMERIZE','source polymer derived from '+methyl,v('methyl','action'),['METHYL_FEED'],['METHYL_SOLID'],[par('reported duration','methyl','duration'),par('vessel type','methyl','vessel'),par('illumination','methyl','illumination')])
 labels=[];dry_ids=[]
 for n,key in enumerate(['material_a','material_b']):
  pre='SULFIDE_'+str(n);monomer=v('bulk',key);label='source polymer derived from '+monomer;labels.append(label);materials.append(dict(id=pre+'_FEED',kind='material_identity_annotation',name=monomer,physical_state_not_reported=True));liquid=pre+'_LIQUID';linked=pre+'_CROSSLINKED';extracted=pre+'_EXTRACTED';dried=pre+'_DRIED';dry_ids.append(dried)
  states += [dict(id=liquid,kind='state',sample=label,state=v('bulk','output_state'),history='after the reported sealed-tube bulk polymerization'),dict(id=linked,kind='state',sample=label,state='crosslinked polymer',history='after reported peroxide/sulfur treatment',same_physical_tube_as_polymerization_not_asserted=True,downstream_dilatometry_consumer_link_not_recovered=True),dict(id=extracted,kind='state',sample=label,state='benzene-extracted crosslinked material'),dict(id=dried,kind='state',sample=label,state='extracted and dried crosslinked polymer',history='after the reported final drying')]
  op(pre+'_POLYMERIZE',label,v('bulk','action'),[pre+'_FEED'],[liquid],[par('initiator','bulk','initiator'),temperature('bulk'),par('vessel type','bulk','vessel')])
  op(pre+'_CROSSLINK',label,v('crosslink','action'),[liquid],[linked],[dict(role='dicumyl peroxide mass fraction',value_raw=v('crosslink','dcp'),unit_raw=v('crosslink','dcp_unit'),reagent_raw=v('crosslink','crosslinker'),source_fragment='crosslink',source_captures=['dcp','dcp_unit','crosslinker']),dict(role='sulfur mass fraction',value_raw=v('crosslink','sulfur'),unit_raw=v('crosslink','sulfur_unit'),reagent_raw=v('crosslink','sulfur_form'),source_fragment='crosslink',source_captures=['sulfur','sulfur_unit','sulfur_form']),temperature('crosslink'),par('vessel type','crosslink','vessel')])
  op(pre+'_EXTRACT',label,v('posttreatment','extraction'),[linked],[extracted],[par('extraction solvent','posttreatment','solvent')])
  op(pre+'_DRY',label,v('posttreatment','drying'),[extracted],[dried],[temperature('posttreatment'),par('pressure','posttreatment','pressure','pressure_unit'),par('duration','posttreatment','duration','duration_unit')])
  for j,(before,after) in enumerate(zip(['POLYMERIZE','CROSSLINK','EXTRACT'],['CROSSLINK','EXTRACT','DRY'])):orders.append(dict(id=pre+'_SEQUENCE_'+str(j),kind='order',before=pre+'_'+before,after=pre+'_'+after,relation='precedes',basis='explicit these liquids/crosslinked materials and finally, with source-verified antecedents'))
 bindings.append(dict(id='EXISTING_BULK_METHOD_SCOPE',kind='binding',existing_process_target=r['existing_bulk_method']['path'],existing_sample_targets=r['existing_sulfide_sample_targets'],named_material_method_instances=labels,material_scope='these two source-named products only; the generic family name is not an assertion that methyl sulfide used this recipe',methyl_branch_excluded=True,not_a_physical_batch_transfer=True))
 for i in [15,16,17]:bindings.append(dict(id='RETAINED_DRYING_PARAMETER_SCOPE_'+str(i),kind='binding',existing_property_process_parameter='@property:/property_series/'+str(i),applies_to_samples=labels,output_states=dry_ids,stage='after crosslinked sulfide benzene extraction, not ether torsion-flex treatment',original_property_content_or_consumer_bindings_modified=False))
 return dict(proposal_id=r['proposal_id'],materials=materials,operations=ops,parameters=[],states=states,orders=orders,bindings=bindings,saved_fragments=f,ether_molding_completion=dict(existing_method=r['existing_ether_method']['path'],existing_sample_targets=r['existing_ether_sample_targets'],mold=v('ether_molding','mold'),pressure=v('ether_molding','pressure'),pressure_magnitude_unknown=True),source_approval_path=a['path'],source_approval_sha256=a['sha256'],material_names_are_separate_method_instances_not_a_pooled_batch=True,new_pdf_information_extracted=0)


def main():
 pp=OUT/'process_relation_trial_011/freeze.json';parent=read(pp);approved={x['reference_no']:x for x in read(OUT/'saved_sulfide_ether_methods_recovery/source_reviews/manifest.json')['papers']};rows=[];repairs=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no'] in approved:
   a=approved[p['reference_no']];assert sha(a['path'])==a['sha256'];ap=read(a['path']);assert sha(ap['proposal_path'])==ap['proposal_sha256'];r=read(ap['proposal_path'])['proposals'][0];old=read(p['candidate_path']);new=deepcopy(old);new[EXTENSION]=[build(r,a)];parts=r['existing_ether_method']['path'].strip('/').split('/');method=new[parts[0]]['process_steps'][int(parts[-1])]
   for field,capture in [('mold','mold'),('pressure','pressure')]:
    assert field not in method['parameters'];value=r['fragments']['ether_molding']['captures'][capture]['value_raw'];method['parameters'][field]=value;repairs.append(dict(reference_no=p['reference_no'],path=r['existing_ether_method']['path']+'/parameters/'+field,before_field_absent=True,after=value,source_fragment='ether_molding',source_capture=capture,source_approval_path=a['path'],source_approval_sha256=a['sha256']))
   dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new);row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  rows.append(row)
 save(TRIAL/'process_parameter_additions.json',dict(additions=repairs,original_property_fields_modified=False,reference_values_used_as_prediction_inputs=False))
 save(TRIAL/'freeze.json',dict(version='process_relation_trial_012',parent_trial='process_relation_trial_011',parent_trial_freeze_sha256=sha(pp),baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),proposal_generation_code_sha256=sha(OUT/'propose_saved_sulfide_and_ether_methods.py'),process_parameter_additions_sha256=sha(TRIAL/'process_parameter_additions.json'),papers=rows,papers_total=101,cumulative_changed_papers=sum(bool(p.get('changed_from_parent')) for p in rows),changed_papers_this_round=1,property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,existing_process_fields_added=len(repairs),reference_answers_or_scores_used_as_prediction_inputs=False,reference_seen_previously_during_error_diagnosis=True,new_pdf_information_extracted=0,stable_workflow_release=False,external_api_calls=0));print({'papers':101,'changed_this_round':1,'parameters_added_to_existing_ether_method':len(repairs),'cumulative_changed_papers':sum(bool(p.get('changed_from_parent')) for p in rows)})

if __name__=='__main__':main()
