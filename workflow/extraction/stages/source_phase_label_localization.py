"""Promote a uniquely witnessed component-specific Tg header into a local label."""
import copy
import math
import re
from stages.table_grid import parse_table_cells
from stages.source_response_header_consistency import response_headers
from stages.stage4_direct_table_supplement import plain, table_cell_scalar, canonical_unit, evidence

VERSION='1.0.0'


def repair(stage4,stage0):
    result=copy.deepcopy(stage4);changes=[]
    tables={b['block_id']:b for b in stage0['elements'] if b['type']=='table'}
    grids={}
    for series in result.get('property_series',[]):
        for point in series.get('points',[]):
            old=point.get('property_name_raw') or series.get('property_name_raw') or ''
            if not re.search(r't[\s_{}]*g|glass.transition',old,re.I):continue
            unit=point.get('unit_raw') or series.get('unit_raw') or point.get('unit_normalized') or series.get('unit_normalized')
            normalized=point.get('unit_normalized') or series.get('unit_normalized') or unit
            if canonical_unit(unit)!='°C' or canonical_unit(normalized)!='°C':continue
            value=table_cell_scalar(point.get('value_raw',''))
            if value is None:continue
            low,high=point.get('value_min'),point.get('value_max')
            if low is not None and not math.isclose(float(low),value,abs_tol=1e-9):continue
            if high is not None and not math.isclose(float(high),value,abs_tol=1e-9):continue
            locs={}
            for proof in point.get('evidence',[]):
                table=tables.get(proof.get('block_id'))
                locator=proof.get('table_locator') or {}
                if not table:continue
                cell=next((c for c in table.get('table_cells',[]) if c['cell_id']==locator.get('cell_id')),None)
                scalar=table_cell_scalar((cell or {}).get('text',''))
                if scalar is not None and math.isclose(scalar,value,abs_tol=1e-9):
                    locs[(table['block_id'],cell['cell_id'])]=(table,cell)
            if len(locs)!=1:continue
            table,cell=next(iter(locs.values()))
            body=table.get('table_body') or table.get('text') or ''
            if '<table' not in body.lower():continue
            if table['block_id'] not in grids:
                grids[table['block_id']]={c.cell_id:c.model_dump() for c in parse_table_cells(body,table['block_id'])}
            grid=grids[table['block_id']]
            if grid.get(cell['cell_id'],{}).get('text')!=cell['text']:continue
            headers,_=response_headers(table,cell)
            if any(grid.get(h['cell_id'],{}).get('text')!=h['text'] for h in headers):continue
            header=' | '.join(dict.fromkeys(plain(h['text']) for h in headers))
            components=set(re.findall(r'\b(?:EPDM|PP)\b',header))
            if len(components)!=1 or not re.search(r't[\s_{}]*g',header,re.I) or '°c' not in re.sub(r'\s','',header).lower():continue
            component=next(iter(components))
            if re.search(r'\b'+component+r'\b',old):continue
            # Literal hierarchy, not a fabricated phase formula or new measurement.
            point['property_name_raw']=header
            proofs=[evidence({'table_id':table['block_id'],'page':table['page'],'bbox':table.get('bbox')},
                        h,row_label='response header',column_label=h['text']) for h in headers]
            for proof in proofs:
                if proof not in point['evidence']:point['evidence'].append(proof)
            changes.append({'record_id':series['series_id']+':'+point['point_id'],
                'before':old,'after':header,'actual_cell_id':cell['cell_id'],'source_proof':proofs})
    return result,{'version':VERSION,'changes':changes,'reference_answers_loaded':False,
                  'values_units_methods_and_samples_changed':False}


