"""Recover actual viscosity specimens from an old table plus its saved footnote."""
import re
from decimal import Decimal
from prepare_audit import OUT,read,save,sha,canonical
from propose_saved_parallel_electrochemical_routes import capture

DEST=OUT/'saved_table_viscosity_specimens_recovery'


def parse_table(text):
 rows=[];previous=None;offset=0
 for line in text.splitlines(keepends=True):
  cells=[x.strip() for x in line.strip().split('|')]
  if len(cells)==11 and (cells[0].isdigit() or cells[0]=='[continuation]'):
   cells_raw=[];start=0
   for cell in line.strip().split('|'):
    a=line.index(cell,start);cells_raw.append(dict(raw=cell.strip(),span=[offset+a,offset+a+len(cell)]));start=a+len(cell)+1
   vals=dict(zip(['polymer','R1','R2','type','monomer_concentration','viscosity','DMF','DMF_LiCl','DMSO','nitrogen','appearance'],cells))
   for key in ['polymer','R1','R2','type']:
    if vals[key] in ['[continuation]','[blank]']:assert previous;vals[key]=previous[key]
   vals.update(saved_row_index=len(rows),row_span=[offset,offset+len(line.rstrip('\r\n'))],cells=cells_raw);rows.append(vals);previous=vals
  offset+=len(line)
 return rows


def main():
 manifest=[]
 for item in read(OUT/'existing_evidence_recovery_inputs/manifest.json')['papers']:
  assert sha(item['path'])==item['sha256'];cache=read(item['path']);qs=[q for q in cache['source_quotations'] if q['text'].startswith('Table 1. Structure and properties of the aromatic polyureas') and 'a Determined at' in q['text'] and '0.5 g' in q['text']];proposals=[]
  if qs:
   q=max(qs,key=lambda q:len(q['text']));rows=parse_table(q['text']);pred=read(OUT/'candidate_v10'/(cache['reference_no']+'.json'));g=pred['process_graph'];cap=capture(q['text'],r'a Determined at (?P<measurement_temperature>20)°C in (?P<medium>DMF\+LiCl) for a (?P<polymer_concentration>0\.5) g dL⁻¹ polymer solution');anchors=[]
   for i,s in enumerate(g['states']):
    if not re.fullmatch(r'PU\d+v\d+',s['id']):continue
    m=re.match(r'PU(?P<polymer>\d+): R1=(?P<R1>[A-H]) .*?R2=(?P<R2>[A-H]) ',s['identity']);c=re.search(r'monomer concentration (?P<conc>[\d.]+)%',s['state']);assert m and c;anchors.append((m.group('polymer'),m.group('R1'),m.group('R2'),Decimal(c.group('conc')),dict(pointer='/process_graph/states/'+str(i),value_sha256=canonical(s),id=s['id'],identity=s['identity'])))
   for row in rows:
    if not re.fullmatch(r'\d+\.\d+',row['viscosity']):continue
    match,=[x[4] for x in anchors if x[:4]==(row['polymer'],row['R1'],row['R2'],Decimal(row['monomer_concentration']))];row['existing_identity_anchor']=match
   vis,=[dict(pointer='/process_graph/states/'+str(i),value_sha256=canonical(s)) for i,s in enumerate(g['states']) if s['id']=='VIS']
   proposals=[dict(proposal_id='saved_table_numeric_viscosity_specimens',saved_table_quote=q,text_sha256=canonical(q['text']),footnote_captures=cap,parsed_rows=rows,existing_generic_viscosity_anchor=vis,does_not_promote_measurement_temperature_to_dissolution_temperature=True,does_not_infer_LiCl_dose_or_reaction_addition=True,requires_source_review=True,not_accepted_into_prediction=True)]
  dest=DEST/'papers'/(cache['reference_no']+'.json');save(dest,dict(reference_no=cache['reference_no'],cache_path=item['path'],cache_sha256=item['sha256'],proposals=proposals,reference_answers_or_scores_read=False,source_pdf_or_stage0_read=False,reference_seen_previously_for_diagnosis=True,external_api_calls=0));manifest.append(dict(reference_no=cache['reference_no'],path=str(dest),sha256=sha(dest),proposals=len(proposals)))
 save(DEST/'manifest.json',dict(papers=manifest,papers_scanned=len(manifest),generator_code_sha256=sha(__file__),reference_answers_or_scores_read=False,source_pdf_or_stage0_read=False,external_api_calls=0));print(dict(scanned=len(manifest),proposed=[x['reference_no'] for x in manifest if x['proposals']]))


if __name__=='__main__':main()
