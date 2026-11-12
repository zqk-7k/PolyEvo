"""Narrow, evidence-bound corrections of incompatible property definitions."""
import copy
import re
from stages.source_table_relations import witness, norm


def repair_property_semantics(stage4,stage0,column_contexts=()):
    out=copy.deepcopy(stage4)
    blocks={b['block_id']:b for b in stage0['elements']}
    columns={}
    for c in column_contexts:
        proofs=[witness(e,blocks) for e in c.get('evidence',[])]
        if proofs and all(proofs):columns[c['table_id'],int(c['column_index'])]=(c,proofs)
    audit=[]
    for row in [*out.get('properties',[]),*out.get('property_series',[])]:
        old=row.get('property_name_normalized') or row.get('property_name_raw') or ''
        context=row.get('measurement_context') or {}
        frequency=context.get('frequency') or {}
        if old=='dielectric_constant_dc' and (frequency.get('value') or 0)>0:
            ev=frequency.get('evidence',[])
            verified=[e for e in ev if e.get('source_sentence') and e['source_sentence'] in (blocks.get(e['block_id'],{}).get('text') or '')]
            if verified:
                row['property_name_normalized']='dielectric_constant'
                audit.append({'id':row.get('property_id') or row.get('series_id'),'before':old,'after':'dielectric_constant',
                              'reason':'explicit nonzero measurement frequency contradicts a DC-only property label','evidence':verified})
        if not re.search(r'viscosity|viscosit',old,re.I):continue
        own=[]
        for point in row.get('points',[row]):
            for ev in point.get('evidence',[]):
                loc=ev.get('table_locator') or {}
                block=blocks.get(ev.get('block_id'),{})
                cell=next((c for c in block.get('table_cells',[]) if c['cell_id']==loc.get('cell_id')),None)
                if cell and (block['block_id'],cell['column_index']) in columns:
                    own.append(columns[block['block_id'],cell['column_index']])
        kinds=[]
        for c,proof in own:
            label=c.get('property_label','')
            for word in ['inherent','intrinsic','reduced','specific']:
                if word in label.casefold() and any(word in p['source_sentence'].casefold() for p in proof):
                    kinds.append((word+'_viscosity',proof))
        if kinds and len({k for k,p in kinds})==1 and old!=kinds[0][0]:
            name,proof=kinds[0]
            row['property_name_normalized']=name
            row['property_name_raw']=name.replace('_',' ')
            for p in proof:
                if p not in row['evidence']:row['evidence'].append(p)
            audit.append({'id':row.get('property_id') or row.get('series_id'),'before':old,'after':name,
                          'reason':'own table column and verbatim footnote define this viscosity','evidence':proof})
    return out,{'changes':audit,'gold_used':False,'records_deleted':0}
