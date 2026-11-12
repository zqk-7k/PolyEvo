"""Recover a direct scalar only when source row, response and unit all agree.

No numeric lookup across samples, no unit inference, no benchmark dependency.
The archived locator and emitted specimen must independently identify the same
printed row. Ranges, display scales and physical conversions are untouched.
"""
import copy
import re
from stages.table_grid import parse_table_cells
from stages.source_table_relations import entries, norm
from stages.stage4_direct_table_supplement import (
    plain, table_cell_scalar, canonical_unit, header_applies, evidence)

VERSION='1.0.1'


def repair_identity_scalars(stage4, stage0, samples=()):
    out=copy.deepcopy(stage4)
    specimens={s['sample_id']:s for s in samples}
    blocks={b['block_id']:b for b in stage0['elements']}
    grids={};changes=[]
    for row,parent,rid in entries(out):
        specimen=specimens.get(row.get('sample_id') or (parent or {}).get('sample_id'),{})
        label=specimen.get('sample_label_raw')
        name=row.get('property_name_raw') or (parent or {}).get('property_name_raw')
        rawunit=row.get('unit_raw') or (parent or {}).get('unit_raw')
        normalized=row.get('unit_normalized') or (parent or {}).get('unit_normalized') or rawunit
        # A missing raw unit is not an inferred conversion: the original header
        # must independently print Celsius below. Explicit differing units abstain.
        rawunit=rawunit or normalized
        if not label or not name or canonical_unit(rawunit)!='°C' or canonical_unit(normalized)!='°C':
            continue
        old=table_cell_scalar(row.get('value_raw',''))
        if old is None:continue
        low,high=row.get('value_min'),row.get('value_max')
        if low is not None and high is not None and low!=high:continue
        locations={}
        for proof in row.get('evidence',[]):
            block=blocks.get(proof.get('block_id'),{})
            if block.get('type')!='table':continue
            locator=proof.get('table_locator') or {}
            cell=next((c for c in block.get('table_cells',[]) if c['cell_id']==locator.get('cell_id')),None)
            if cell and table_cell_scalar(cell.get('text','')) is not None:
                locations[(block['block_id'],cell['cell_id'])]=(block,cell)
        if len(locations)!=1:continue
        block,cell=next(iter(locations.values()))
        body=block.get('table_body') or block.get('text') or ''
        if not body or '<table' not in body.lower():continue
        if block['block_id'] not in grids:
            grids[block['block_id']]={c.cell_id:c.model_dump() for c in parse_table_cells(body,block['block_id'])}
        grid=grids[block['block_id']]
        if grid.get(cell['cell_id'],{}).get('text')!=cell['text']:continue
        # A wrong locator can point at the adjacent specimen's value. Use its
        # response COLUMN, never its number, to find the unique printed specimen
        # row. Both the sample and the complete header must independently agree.
        left=[c for c in block['table_cells'] if
              c['column_index']<cell['column_index'] and norm(c.get('text',''))==norm(label)]
        if len(left)!=1 or grid.get(left[0]['cell_id'],{}).get('text')!=left[0]['text']:continue
        target=[c for c in block['table_cells'] if c['row_index']==left[0]['row_index'] and
                c['column_index']==cell['column_index'] and c.get('row_span',1)==1 and
                c.get('column_span',1)==1]
        if len(target)!=1:continue
        target=target[0]
        if grid.get(target['cell_id'],{}).get('text')!=target['text']:continue
        data_rows=[c['row_index'] for c in block['table_cells'] if
                   c['column_index']==cell['column_index'] and table_cell_scalar(c.get('text','')) is not None]
        boundary=min(data_rows) if data_rows else cell['row_index']
        headers=[h for h in block['table_cells'] if h['row_index']<boundary and header_applies(h,cell)]
        header=' | '.join(dict.fromkeys(plain(h['text']) for h in headers))
        if norm(plain(name))!=norm(header) or '°c' not in re.sub(r'\s+','',header).casefold():continue
        if re.search(r'10\s*(?:\^|\*\*|[⁰¹²³⁴⁵⁶⁷⁸⁹])',header):continue
        value=table_cell_scalar(target['text'])
        if value is None or value==old:continue
        before={k:row.get(k) for k in ('value_raw','value_min','value_max')}
        row.update(value_raw=format(value,'.12g'),value_min=value,value_max=value)
        proof=evidence({'table_id':block['block_id'],'page':block['page'],'bbox':block.get('bbox')},
                       target,row_label=left[0]['text'],column_label=header)
        if proof not in row['evidence']:row['evidence'].append(proof)
        changes.append({'record_id':rid,'before':before,'after':value,'evidence':proof,
                        'original_locator':cell['cell_id'],
                        'reason':'Unique exact printed specimen row, unchanged response column, response hierarchy, unit and direct scalar cell agree'})
    return out,{'version':VERSION,'changes':changes,'reference_answers_loaded':False,
                'sample_identities_changed':False,'new_measurements_created':False}
