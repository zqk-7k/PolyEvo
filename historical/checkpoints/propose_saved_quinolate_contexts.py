"""Read predictions and their saved quotations only; no reference or scores."""
import re
from prepare_audit import OUT,read,save,sha,canonical

DEST=OUT/'saved_quinolate_context_recovery'
PATTERNS={
 'protected_ligand_outcome':re.compile(r'with (?P<scope>methoxy-protected ligands), the (?P<bond>O-Me) bond was readily (?P<change>cleaved) under formation of the (?P<product>boron quinolate)\s+moiety and (?P<byproduct>MeBr)'),
 'gpc_mobile_phase':re.compile(r'(?P<sample>PSBPhQ-C6H4NMe2).*?\[(?P<salt>Bu4N)\]Br \((?P<loading>0\.2 wt %)\).*?(?P<outcome>monomodal trace)',re.S),
 'photograph_excitation':re.compile(r'(?P<method>Photographs) of solutions of (?P<series>PSBPhQ-X) in (?P<solvent>THF).*?(?P<excitation>black light)\s+at (?P<wavelength>365) (?P<unit>nm).*?X \) (?P<members>Bpin, C6F5, H, Cl, C6H4OMe, C6H4NMe2)',re.S)}


def main():
 rows=[]
 for p in read(OUT/'candidate_v10/freeze.json')['papers']:
  assert sha(p['candidate_path'])==p['candidate_sha256'];pred=read(p['candidate_path']);pg=pred.get('process_graph',{});cp=OUT/'existing_evidence_recovery_inputs/papers'/(p['reference_no']+'.json');cache=read(cp);proposals=[]
  if any('quinolate' in str(s.get('identity','')).lower() or 'PSBPhQ' in str(s.get('identity','')) for s in pg.get('states',[])):
   for method,pattern in PATTERNS.items():
    matches=[(q,pattern.search(q['text'])) for q in cache['source_quotations'] if pattern.search(q['text'])]
    if not matches:continue
    q,m=min(matches,key=lambda qm:len(qm[0]['text']))
    row=dict(proposal_id=method,method=method,existing_quote=q,matched_quote_span=list(m.span()),captures={k:dict(value_raw=v,original_quote_span=list(m.span(k))) for k,v in m.groupdict().items()})
    if method=='protected_ligand_outcome':
     targets=[]
     for i,op in enumerate(pg.get('operations',[])):
      for j,par in enumerate(op.get('parameters',[])):
       if par.get('role')=='ligand' and '8-methoxyquinoline' in str(par.get('value','')):
        targets.append(dict(path=f'/process_graph/operations/{i}/parameters/{j}',samples=par['applies_to'],operation_id=op['id']))
     if not targets:continue
     row['existing_targets']=targets
    elif method=='gpc_mobile_phase':
     targets=[dict(path='/process_graph/states/'+str(i),state_id=s['id'],identity=s['identity']) for i,s in enumerate(pg.get('states',[])) if s.get('identity')==m['sample'] and str(s.get('id','')).startswith('dry_')]
     methods=[z for z in cache['source_quotations'] if 'GPC-MALLS' in z['text'] and '0.2% Bu4NBr in THF' in z['text']]
     if len(targets)!=1 or not methods:continue
     row['existing_targets']=targets;row['medium_method_quote']=min(methods,key=lambda z:len(z['text']))
    else:
     members=['PSBPhQ-'+s.strip() for s in m['members'].split(',')];targets=[]
     for member in members:
      choices=[dict(path='/process_graph/states/'+str(i),state_id=s['id'],identity=member) for i,s in enumerate(pg.get('states',[])) if s.get('identity')==member and str(s.get('id','')).startswith('photo_')]
      if len(choices)==1:targets+=choices
     if len(targets)!=len(members):continue
     row['existing_targets']=targets
    proposals.append(row)
  dest=DEST/'papers'/(p['reference_no']+'.json');save(dest,dict(reference_no=p['reference_no'],candidate_input=p,property_source=pred['property_source'],cache_path=str(cp),cache_sha256=sha(cp),proposals=proposals,accepted_into_prediction=False,reference_answers_or_scores_read=False,new_pdf_information_extracted=0,external_api_calls=0))
  rows.append(dict(reference_no=p['reference_no'],path=str(dest),sha256=sha(dest),proposals=len(proposals)))
 save(DEST/'manifest.json',dict(papers=rows,papers_scanned=len(rows),groups=sum(x['proposals'] for x in rows),generator_code_sha256=sha(__file__),reference_answers_or_scores_read=False,new_pdf_information_extracted=0,external_api_calls=0))
 print({'scanned':len(rows),'groups':sum(x['proposals'] for x in rows),'nonempty_papers':[x['reference_no'] for x in rows if x['proposals']]})

if __name__=='__main__':main()
