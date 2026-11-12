"""Apply approved source-only records as a separate process extension."""
from copy import deepcopy
from prepare_audit import OUT,read,save,sha

TRIAL=OUT/'process_relation_trial_004'


def build_group(r,approval):
 f=r['fragments']
 def value(fragment,key):return f[fragment]['captures'][key]['value_raw']
 def param(role,fragment,key,component_key=None):
  p=dict(role=role,value_raw=value(fragment,key),source_fragment=fragment,source_capture=key)
  if component_key:p.update(component_raw=value(fragment,component_key),component_source_capture=component_key)
  return p
 if r['method']=='source_local_vcl3_bottle_recipe':
  ops=[dict(id='V_PURGE',kind='operation',name='Flush the reported pressure bottle with dry nitrogen',
    equipment='reported pressure bottle',parameters=[param('bottle volume','charge','volume'),param('purge gas','charge','gas')]),
   dict(id='V_CHARGE',kind='operation',name='Charge monomer and anhydrous VCl3 into the reported bottle',output_state='V_CHARGED',
    parameters=[param('monomer charge','charge','monomer_amount'),param('VCl3 charge','charge','v_amount','v_identity')]),
   dict(id='V_INITIATE',kind='operation',name='Cap the bottle and inject the reported aluminum reagent',input_state='V_CHARGED',output_state='V_INITIATED',
    parameters=[param('self-sealing cap','initiation','cap'),param('aluminum reagent charge','initiation','al_amount','al_identity'),param('injection device','initiation','injector')]),
   dict(id='V_TUMBLE',kind='operation',name='Tumble the caged reaction bottle in the reported water bath',input_state='V_INITIATED',output_state='V_POST_REACTION',
    parameters=[param('bottle cage','reaction','cage'),param('agitation','reaction','agitation'),param('duration','reaction','duration'),param('temperature','reaction','temperature'),param('bath','reaction','bath')])]
  states=[dict(id='V_CHARGED',kind='state',state='source-reported monomer/VCl3 charge after nitrogen flushing; physical phase not assigned',operation='V_CHARGE'),
   dict(id='V_INITIATED',kind='state',state='sealed reaction contents after aluminum-reagent injection; pressure magnitude not assigned',operation='V_INITIATE'),
   dict(id='V_POST_REACTION',kind='state',state='reaction contents after the recorded bottle tumbling; conversion and crystallinity not assigned',operation='V_TUMBLE')]
  orders=[dict(id=f'V_ORDER{i+1}',kind='order',before=a,after=b,relation='source_reported_procedural_and_vessel_sequence') for i,(a,b) in enumerate([('V_PURGE','V_CHARGE'),('V_CHARGE','V_INITIATE'),('V_INITIATE','V_TUMBLE')])]
 elif r['method']=='source_local_crystallization_conditioning':
  ops=[dict(id='C_HEAT',kind='operation',name='Condition polymers in hot Soxhlet with boiling acetone',output_state='C_CONDITIONED',
    parameters=[param('equipment','heat','apparatus'),param('medium','heat','medium'),param('duration','heat','duration')]),
   dict(id='C_FILTER',kind='operation',name=value('post','filter'),input_state='C_CONDITIONED',output_state='C_FILTERED',parameters=[]),
   dict(id='C_DRY',kind='operation',name='Dry the filtered conditioning-treated polymers',input_state='C_FILTERED',output_state='C_DRIED',
    parameters=[param('duration','post','duration'),param('temperature','post','temperature'),param('pressure condition','post','pressure')])]
  states=[dict(id='C_CONDITIONED',kind='state',state='polymers subjected to the reported crystallization-conditioning method; success not guaranteed',operation='C_HEAT'),
   dict(id='C_FILTERED',kind='state',state='filtered conditioning-treated polymers',operation='C_FILTER'),
   dict(id='C_DRIED',kind='state',state='conditioning-treated polymers after the reported vacuum drying',operation='C_DRY')]
  orders=[dict(id='C_ORDER1',kind='order',before='C_HEAT',after='C_FILTER',relation='explicit_then_same_paragraph_anaphora'),dict(id='C_ORDER2',kind='order',before='C_FILTER',after='C_DRY',relation='source_reported_filter_then_dry')]
 else:
  assert r['method']=='source_local_polymer_oven_drying'
  ops=[dict(id='W_DRY',kind='operation',name='Dry the polymer in the reported vacuum oven',output_state='W_DRIED',
   parameters=[param('temperature','dry','temperature'),param('equipment','dry','equipment')])]
  states=[dict(id='W_DRIED',kind='state',state='polymer after the reported oven drying; prior treatment and drying duration not reconstructed',operation='W_DRY')];orders=[]
 bindings=[dict(id=op['id']+'_SCOPE',kind='binding',operation_id=op['id'],relation='applies_within_this_reported_source_local_method',
  input_state=op.get('input_state'),output_state=op.get('output_state'),individual_native_sample_assignments=[],
  no_inheritance_of_original_native_output_list=True) for op in ops]
 return dict(proposal_id=r['proposal_id'],method=r['method'],original_common_source_block_id=r['source_block_id'],
  method_scope='source-local stated procedure; no individual polymer-row/catalyst assignment inferred',
  operations=ops,states=states,orders=orders,bindings=bindings,source_quotation_fragments=f,
  source_approval_path=approval['path'],source_approval_sha256=approval['sha256'],existing_quote_values_only=True,
  no_solvent_absence_claim=True,no_unreported_sample_preparation_or_crystallinity_claim=True,
  no_cross_method_order_or_native_product_assignment=True,new_pdf_information_extracted=0)


def main():
 parent_path=OUT/'process_relation_trial_003/freeze.json';parent=read(parent_path)
 approved=read(OUT/'saved_bottle_and_crystallization/source_reviews/manifest.json');byref={a['reference_no']:a for a in approved['papers']};papers=[]
 for p in parent['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];row=deepcopy(p);row['changed_from_immediate_parent']=False
  if p['reference_no'] in byref:
   a=byref[p['reference_no']];assert sha(a['path'])==a['sha256'];approval=read(a['path']);assert approval['trial_only']
   assert sha(approval['proposal_path'])==approval['proposal_sha256'];proposal=read(approval['proposal_path']);assert proposal['candidate_input']['candidate_sha256']==p['candidate_sha256']
   old=read(p['candidate_path']);new=deepcopy(old);groups=[]
   for d in approval['groups']:
    assert d['decision']=='supported_for_separate_process_side_trial';r=next(x for x in proposal['proposals'] if x['proposal_id']==d['proposal_id'])
    for f in r['fragments'].values():
     for v in f['captures'].values():
      start,end=v['original_quote_span'];assert f['existing_quote']['text'][start:end]==v['value_raw']
    groups.append(build_group(r,a))
   new['process_saved_bottle_crystallization_recovery']=groups;assert {k:v for k,v in new.items() if k!='process_saved_bottle_crystallization_recovery'}==old
   dest=TRIAL/'papers'/(p['reference_no']+'.json');save(dest,new)
   row.update(candidate_path=str(dest),candidate_sha256=sha(dest),changed_from_parent=True,changed_from_immediate_parent=True,
    immediate_parent_candidate_path=p['candidate_path'],immediate_parent_candidate_sha256=p['candidate_sha256'])
  papers.append(row)
 save(TRIAL/'freeze.json',dict(version='process_relation_trial_004',parent_trial='process_relation_trial_003',parent_trial_freeze_sha256=sha(parent_path),
  baseline_candidate='candidate_v10',baseline_candidate_freeze_sha256=sha(OUT/'candidate_v10/freeze.json'),
  prediction_application_code_sha256=sha(__file__),proposal_generation_code_sha256=read(OUT/'saved_bottle_and_crystallization/manifest.json')['generator_code_sha256'],
  papers=papers,papers_total=len(papers),cumulative_changed_papers=sum(x.get('changed_from_parent',False) for x in papers),
  changed_papers_this_round=sum(x['changed_from_immediate_parent'] for x in papers),old_properties_and_bindings_modified=False,
  reference_answers_or_scores_used_as_prediction_inputs=False,new_pdf_information_extracted=0,
  all101_scientific_targets_proven=False,stable_workflow_release=False,external_api_calls=0))
 print({'papers':len(papers),'changed_this_round':sum(x['changed_from_immediate_parent'] for x in papers),'cumulative_changed_papers':sum(x.get('changed_from_parent',False) for x in papers)})


if __name__=='__main__':main()
