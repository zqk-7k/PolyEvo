"""Apply verified frozen-quote recovery and two documented input repairs."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha

TRIAL=OUT/'process_relation_trial_016'
EXTENSION='process_saved_parallel_electrochemical_routes_recovery'


def build(proposal,approval,old):
 fragments=deepcopy(proposal['fragments']);states=[];ops=[];bindings=[];orders=[];materials=[];clause_spans=[]
 native=old['native_process_context'];labels={x['sample_id']:x['sample_label_raw'] for x in native['samples']}
 def value(fragment,key):return fragments[fragment]['captures'][key]['value_raw']
 def par(role,fragment,key,unit=None):return dict(role=role,value_raw=value(fragment,key),unit_raw=unit,source_fragment=fragment,source_capture=key)
 def clause(role,fragment,start,end=None):
  text=fragments[fragment]['existing_quote']['text'];a=text.index(start);b=text.index(end,a)+len(end) if end else a+len(start);ident='CLAUSE_'+str(len(clause_spans));clause_spans.append(dict(id=ident,source_fragment=fragment,value_raw=text[a:b],original_quote_span=[a,b]));return dict(role=role,value_raw=text[a:b],source_clause=ident)
 def mat(ident,sample_id=None,identity=None):
  row=dict(id=ident,kind='material_identity_annotation',identity=identity if identity else labels[sample_id],not_a_physical_state=True)
  if sample_id is not None:
   i=next(i for i,x in enumerate(native['samples']) if x['sample_id']==sample_id);row['existing_material_identity_target']='/native_process_context/samples/'+str(i)
  materials.append(row);return ident
 def state(ident,identity,stage,description,frags,**extra):
  states.append(dict(id=ident,kind='state',identity=identity,stage=stage,state=description,source_fragments=frags,**extra));return ident
 def operation(ident,name,inputs,outputs,params,frags,scope):
  ops.append(dict(id=ident,kind='operation',name=name,scope=scope,inputs=inputs,outputs=outputs,parameters=params,source_fragments=frags,not_a_pooled_batch=True))
 def bind(ident,op,inputs,outputs,scope,frags):bindings.append(dict(id=ident,kind='binding',operation_id=op,input_nodes=inputs,output_states=outputs,scope=scope,source_fragments=frags,physical_batch_continuity_not_inferred=True))
 def order(ident,before,after,scope,frags):orders.append(dict(id=ident,kind='order',before=before,after=after,scope=scope,relation='precedes_within_reported_method_application',source_fragments=frags))
 m1=mat('M_PMTM1','s001');m2=mat('M_PMTM2','s002')
 for sid in ['s003','s005','s006','s008','s009','s010','s011','s013']:mat('M_'+sid,sid)
 # The shared precursor workup is applied separately to the two existing
 # AIBN-polymerization outputs. No two-batch pooling or extra final dry is made.
 g='precursor_workup';previous={}
 for code in ['PMTM1','PMTM2']:
  for stage,description in [('REACTED','polymer-containing reaction mixture after free-radical polymerization'),('PRECIPITATED','polymer precipitated from the reaction mixture into methanol'),('FILTERED','filtered precipitated precursor polymer'),('DRIED','precursor dried in vacuo before repeated-precipitation purification'),('PURIFIED','precursor purified by repeated precipitations; subsequent drying conditions not recovered')]:state(code+'_'+stage,code,stage,description,[g])
 stages=[('POLY','REACTED',value(g,'polymerization'),[par('initiator',g,'initiator')]),('PRECIP','PRECIPITATED',value(g,'precipitate'),[clause('precipitant',g,'methanol')]),('FILTER','FILTERED',value(g,'filter'),[]),('DRY','DRIED',value(g,'dry'),[clause('drying atmosphere',g,'in vacuo')]),('PURIFY','PURIFIED',value(g,'purification'),[clause('repetition qualifier',g,'repeated precipitations')])]
 for opid,stage,name,params in stages:
  inputs=[code+'_'+previous[code] for code in previous];outputs=[code+'_'+stage for code in ['PMTM1','PMTM2']];operation('PRE_'+opid,name,inputs,outputs,params,[g],'shared precursor method, two independent existing batch identities')
  for code in ['PMTM1','PMTM2']:
   bind('PRE_'+opid+'_'+code,'PRE_'+opid,[code+'_'+previous[code]] if code in previous else [],[code+'_'+stage],code,[g]);previous[code]=stage
 for left,right in zip(stages,stages[1:]):order('PRE_'+left[0]+'_'+right[0],'PRE_'+left[0],'PRE_'+right[0],'each precursor batch separately',[g])
 # Parallel PC route. Category GPMTM1 is not a physical input.
 g='pc_galvanostatic';state('PC_COATED','PMTM1 PC branch','before electrolysis','PMTM1-coated platinum electrode',[g]);state('PC_PRODUCT',labels['s005'],'after PC electrolysis','product of coated-PMTM1 electrolysis in propylene carbonate; film appearance not recovered',[g])
 operation('PC_COAT',value(g,'coat'),[m1],['PC_COATED'],[par('support',g,'electrode')],[g],'PMTM1-to-GPMTM1P route')
 operation('PC_ELECTROLYZE',value(g,'electrolyze'),['PC_COATED'],['PC_PRODUCT'],[par('solvent',g,'solvent'),clause('mode','galvanostatic_category','Constant-Current Electrolysis')],[g,'galvanostatic_category'],'PMTM1-to-GPMTM1P route; current/time/temperature not recovered')
 bind('PC_COAT','PC_COAT',[m1],['PC_COATED'],'PC route',[g]);bind('PC_ELECTROLYZE','PC_ELECTROLYZE',['PC_COATED'],['PC_PRODUCT'],'PC route',[g]);order('PC_COAT_ELECTRO','PC_COAT','PC_ELECTROLYZE','PC only',[g])
 # Parallel DCM route. Peeling precedes vacuum drying, as explicitly quoted.
 g='dcm_galvanostatic'
 for ident,stage,description in [('D_SOLUTION','after dissolution','50mg PMTM1 dissolved in dichloromethane before electrolysis'),('D_ANODE_FILM','after electrolysis before peeling','black film on anode after the specified DCM-route electrolysis'),('D_PEELED','after peeling before vacuum drying','black film peeled from the anode'),('D_DRY','after peeling and vacuum drying','vacuum-dried black film GPMTM1D')]:state(ident,'PMTM1 DCM branch' if ident=='D_SOLUTION' else labels['s006'],stage,description,[g])
 operation('D_DISSOLVE',value(g,'dissolve'),[m1],['D_SOLUTION'],[par('PMTM1 mass',g,'mass','mg'),par('solvent',g,'solvent')],[g],'PMTM1-to-GPMTM1D route')
 operation('D_ELECTROLYZE','constant-current electrolysis',['D_SOLUTION'],['D_ANODE_FILM'],[par('current',g,'current','mA'),par('duration',g,'duration','min'),par('temperature verbatim',g,'temperature_raw'),par('atmosphere',g,'atmosphere'),clause('mode','galvanostatic_category','Constant-Current Electrolysis')],[g,'galvanostatic_category'],'DCM route only; not transferred to PC')
 operation('D_PEEL',value(g,'peel'),['D_ANODE_FILM'],['D_PEELED'],[par('support',g,'support')],[g],'GPMTM1D only')
 operation('D_DRY',value(g,'dry'),['D_PEELED'],['D_DRY'],[clause('atmosphere',g,'in vacuo')],[g],'GPMTM1D only; drying temperature/time/pressure unreported')
 for ident,inputs,outputs in [('D_DISSOLVE',[m1],['D_SOLUTION']),('D_ELECTROLYZE',['D_SOLUTION'],['D_ANODE_FILM']),('D_PEEL',['D_ANODE_FILM'],['D_PEELED']),('D_DRY',['D_PEELED'],['D_DRY'])]:bind(ident,ident,inputs,outputs,'DCM branch',[g])
 for left,right in [('D_DISSOLVE','D_ELECTROLYZE'),('D_ELECTROLYZE','D_PEEL'),('D_PEEL','D_DRY')]:order(left+'_'+right,left,right,'DCM branch',[g])
 # Chemical oxidation is recovered only through the saved gray precipitate.
 g='chemical_oxidation';state('CHEM_SOLUTION','PMTM1 chemical branch','before oxidant addition','PMTM1 solution in dichloromethane under a nitrogen blanket',[g]);state('CHEM_REACTED','CPMTM1 chemical branch','after reaction before methanol precipitation','chemical oxidation mixture after the reported reaction interval',[g]);state('CHEM_GRAY',labels['s003'],'after methanol precipitation','gray precipitated chemical oxidation product; later wash/dry not recovered',[g])
 operation('CHEM_DISSOLVE',value(g,'dissolve'),[m1],['CHEM_SOLUTION'],[par('PMTM1 mass',g,'polymer_mass','mg'),par('solvent volume',g,'solvent_volume','mL'),par('solvent',g,'solvent'),clause('atmosphere verbatim',g,'blanket of','in 5 mL')],[g],'CPMTM1 chemical route')
 operation('CHEM_ADD_REACT',value(g,'add'),['CHEM_SOLUTION'],['CHEM_REACTED'],[clause('oxidant identity and amount verbatim',g,'10 g of','in 15 mL'),par('oxidant mass',g,'oxidant_mass','g'),par('oxidant solvent volume',g,'oxidant_solvent_volume','mL'),par('oxidant solvent',g,'oxidant_solvent'),par('addition qualifier',g,'add'),par('reaction duration',g,'duration','h')],[g],'CPMTM1 chemical route')
 operation('CHEM_PRECIP',value(g,'precipitate'),['CHEM_REACTED'],['CHEM_GRAY'],[clause('precipitant',g,'methanol')],[g],'CPMTM1 chemical route')
 for ident,inputs,outputs in [('CHEM_DISSOLVE',[m1],['CHEM_SOLUTION']),('CHEM_ADD_REACT',['CHEM_SOLUTION'],['CHEM_REACTED']),('CHEM_PRECIP',['CHEM_REACTED'],['CHEM_GRAY'])]:bind(ident,ident,inputs,outputs,'CPMTM1 chemical branch',[g])
 order('CHEM_DISSOLVE_ADD','CHEM_DISSOLVE','CHEM_ADD_REACT','CPMTM1',[g]);order('CHEM_ADD_PRECIP','CHEM_ADD_REACT','CHEM_PRECIP','CPMTM1',[g])
 # Pyrrole media are reported jointly; their allocation to each electrolyte
 # is not known. A pre-coated electrode state does not invent a coating recipe.
 g='pyrrole_graft';state('PY_COATED','PMTM2','before pyrrole electropolymerization','PMTM2-coated electrodes; electrode metal and coating recipe not recovered',[g])
 variant_states=[]
 for sid,term in [('s008','PTSA'),('s009','SDS'),('s010','TBAFB')]:
  ident='PY_'+sid;state(ident,labels[sid],'after pyrrole grafting','corresponding doped PMTM2/PPy graft film',['pyrrole_graft','sem_faces_and_wash'],electrolyte_alternative=term,solvent_allocation_unknown=True,wash_status_unspecified=True);variant_states.append(ident)
 params=[par('pyrrole concentration',g,'monomer_concentration','mol/L'),par('supporting electrolyte concentration',g,'electrolyte_concentration','mol/L'),clause('reported electrolyte alternatives',g,'[p-tol','and TBAFB]'),par('reported media; allocation unknown',g,'media'),par('potential',g,'potential','V'),clause('reference electrode verbatim',g,'versus the','reference electrode')]
 operation('PY_ELECTROLYZE',value(g,'operation'),['PY_COATED'],variant_states,params,[g],'three independent electrolyte alternatives; not one combined electrolyte or solvent recipe')
 for sid,term in [('s008','PTSA'),('s009','SDS'),('s010','TBAFB')]:bind('PY_'+sid,'PY_ELECTROLYZE',['PY_COATED'],['PY_'+sid],dict(existing_sample=sid,electrolyte_alternative=term,solvent_allocation_unknown=True),[g,'sem_faces_and_wash'])
 # SEM states have explicit face and wash qualifiers; no invented wash solvent.
 g='sem_faces_and_wash'
 for sid in ['s008','s009']:
  state('SEM_'+sid+'_SOLUTION',labels[sid],'SEM solution face','cauliflower-like solution-face morphology',[g],wash_status_unspecified=True);state('SEM_'+sid+'_ELECTRODE',labels[sid],'SEM electrode face','electrode-face morphology differs from pristine PPy',[g],wash_status_unspecified=True)
 state('BF4_UNWASHED',labels['s010'],'before reported washing; solution face','unwashed BF4-doped film solution side with irregularities',[g]);state('BF4_WASHED',labels['s010'],'after reported washing; solution face','washed BF4-doped film solution side with some irregularities removed',[g],wash_medium_unknown=True,wash_duration_unknown=True)
 operation('BF4_WASH','washing',['BF4_UNWASHED'],['BF4_WASHED'],[],[g],'BF4-doped PMTM2/PPy SEM comparison; medium and duration not recovered');bind('BF4_WASH','BF4_WASH',['BF4_UNWASHED'],['BF4_WASHED'],'BF4 SEM comparison',[g])
 # The pristine PPy control is not a graft or a PMTM2-coated precursor.
 g='pristine_control';state('PPY_CONTROL',labels['s011'],'after separate same-conditions synthesis','pristine PPy comparison film with both faces examined',[g],PMTM2_graft=False)
 operation('PPY_CONTROL_SYNTH','synthesized',[],['PPY_CONTROL'],[clause('comparison condition',g,'Under the same synthesis conditions')],[g],'separately synthesized pristine PPy control');bind('PPY_CONTROL_SYNTH','PPY_CONTROL_SYNTH',[],['PPY_CONTROL'],'pristine PPy, no PMTM2 graft',[g])
 # ACN thiophene route is separate from any un-recovered DCM route.
 g='acn_thiophene_graft';state('TH_PMTM2_COATED','PMTM2 ACN-PTh branch','before thiophene electrolysis','PMTM2-coated platinum anode',[g]);state('TH_ACN_PRODUCT','PMTM2/PTh ACN branch','after specified ACN electrolysis','electropolymerized material on the working anode; black appearance/peeling/drying not recovered',[g])
 operation('TH_COAT',value(g,'coat'),[m2],['TH_PMTM2_COATED'],[par('support',g,'electrode')],[g],'ACN thiophene route only')
 operation('TH_ACN_ELECTRO','electrolysis',['TH_PMTM2_COATED'],['TH_ACN_PRODUCT'],[par('solvent',g,'solvent'),par('thiophene concentration',g,'monomer_concentration','mol/L'),par('electrolyte',g,'electrolyte'),par('electrolyte concentration',g,'electrolyte_concentration','mol/L'),par('potential',g,'potential','V'),par('duration',g,'duration','min'),par('atmosphere',g,'atmosphere')],[g],'PMTM2/PTh ACN coated-anode route only')
 bind('TH_COAT','TH_COAT',[m2],['TH_PMTM2_COATED'],'ACN-PTh',[g]);bind('TH_ACN_ELECTRO','TH_ACN_ELECTRO',['TH_PMTM2_COATED'],['TH_ACN_PRODUCT'],'ACN-PTh',[g]);order('TH_COAT_ELECTRO','TH_COAT','TH_ACN_ELECTRO','ACN-PTh',[g])
 # All additional face states are specimen identity distinctions, not invented
 # physical transfers. Their links are explicitly typed as identity annotations.
 annotations=[]
 for sid in ['s008','s009']:
  for face in ['SOLUTION','ELECTRODE']:annotations.append(dict(id='FACE_'+sid+'_'+face,kind='specimen_identity_annotation',material_state='PY_'+sid,observed_state='SEM_'+sid+'_'+face,relation='same named formulation and face; physical batch identity unknown',not_a_temporal_relation=True))
 annotations.append(dict(id='BF4_SEM_ID',kind='specimen_identity_annotation',material_state='PY_s010',observed_states=['BF4_UNWASHED','BF4_WASHED'],relation='same reported formulation, distinct wash states; physical batch identity unknown',not_a_temporal_relation=True))
 return dict(materials=materials,states=states,operations=ops,bindings=bindings,orders=orders,identity_annotations=annotations,saved_fragments=fragments,additional_verbatim_clause_spans=clause_spans,source_approval_path=approval['path'],source_approval_sha256=approval['sha256'],native_input_repair_basis=['pc_galvanostatic','dcm_galvanostatic'],category_is_not_physical_intermediate=True,media_and_electrolyte_alternatives_not_cartesianized=True,unrecovered_workup_not_invented=True,new_pdf_information_extracted=0)


def main():
 parentpath=OUT/'process_relation_trial_015/freeze.json';parent=read(parentpath);approved=read(OUT/'saved_parallel_electrochemical_routes_recovery/source_reviews/manifest.json')['papers'];assert len(approved)==1;approval=approved[0];assert sha(approval['path'])==approval['sha256'];review=read(approval['path']);assert sha(review['proposal_path'])==review['proposal_sha256'];packet=read(review['proposal_path']);rows=[];repairs=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no']==approval['reference_no']:
   old=read(p['candidate_path']);new=deepcopy(old);new[EXTENSION]=[build(packet['proposals'][0],approval,old)]
   for i,fragment in [(3,'pc_galvanostatic'),(4,'dcm_galvanostatic')]:
    path='/native_process_context/process_steps/'+str(i)+'/input_sample_ids';before=new['native_process_context']['process_steps'][i]['input_sample_ids'];assert before==['s004'];assert packet['proposals'][0]['fragments'][fragment]['captures']['input']['value_raw']=='PMTM1';repairs.append(dict(path=path,before=before,after=['s001'],basis_saved_fragment=fragment));new['native_process_context']['process_steps'][i]['input_sample_ids']=['s001']
   new[EXTENSION][0]['native_input_repairs']=repairs;dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new);row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  rows.append(row)
 save(TRIAL/'freeze.json',dict(version=TRIAL.name,parent_trial='process_relation_trial_015',parent_trial_freeze_sha256=sha(parentpath),baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),prediction_application_code_sha256=sha(__file__),proposal_generation_code_sha256=sha(OUT/'propose_saved_parallel_electrochemical_routes.py'),papers=rows,papers_total=101,changed_papers_this_round=1,cumulative_changed_papers=sum(bool(p.get('changed_from_parent')) for p in rows),documented_process_field_repairs=repairs,property_content_or_bindings_modified=False,frozen_original_outputs_modified=False,reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,stable_workflow_release=False,external_api_calls=0));print(dict(papers=len(rows),changed_this_round=1,explicit_old_process_fields_repaired=len(repairs),cumulative_changed_papers=sum(bool(p.get('changed_from_parent')) for p in rows)))


if __name__=='__main__':main()
