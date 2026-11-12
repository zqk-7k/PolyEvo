"""Repair scalar bounds from one literal table cell, never infer a conversion."""
import copy
import math
import re
from stages.stage4_direct_table_supplement import table_cell_scalar, canonical_unit, header_applies, power_header, plain

VERSION = '1.0.0'


def repair_scalar_bounds(stage4, stage0):
    result = copy.deepcopy(stage4)
    tables = {b['block_id']: b for b in stage0['elements'] if b['type'] == 'table'}
    changes, skipped = [], []
    rows = [(r, None, r['property_id']) for r in result.get('properties', [])]
    rows += [(p, s, s['series_id'] + ':' + p['point_id'])
             for s in result.get('property_series', []) for p in s['points']]
    rows += [(r, None, r['specialized_id']) for r in result.get('specialized_property_observations', [])]
    for row, parent, rid in rows:
        raw = row.get('value_raw')
        if not raw or re.search(r'±|\\pm|[<>≤≥≈~]|\\sim|\\approx', str(raw)):
            continue
        literal = table_cell_scalar(raw)
        if literal is None:
            continue
        candidates = {}
        for proof in row.get('evidence', []):
            table = tables.get(proof.get('block_id'))
            loc = proof.get('table_locator') or {}
            if not table or not loc.get('cell_id'):
                continue
            for cell in table.get('table_cells', []):
                if cell['cell_id'] != loc['cell_id']:
                    continue
                if re.search(r'±|\\pm|[<>≤≥≈~]|\\sim|\\approx', str(cell['text'])):
                    continue
                if table_cell_scalar(cell['text']) == literal:
                    candidates[cell['cell_id']] = (table, cell)
        if len(candidates) != 1:
            continue
        table, cell = next(iter(candidates.values()))
        parent = parent or {}
        raw_unit = row.get('unit_raw') or parent.get('unit_raw')
        normalized_unit = row.get('unit_normalized') or parent.get('unit_normalized') or raw_unit
        if canonical_unit(raw_unit) != canonical_unit(normalized_unit):
            skipped.append({'record_id': rid, 'reason': 'A separate dimensional conversion may be present'})
            continue
        applicable = [h for h in table['table_cells'] if h['row_index'] < cell['row_index']
                      and header_applies(h, cell)]
        unit_and_headers = [raw_unit or '', normalized_unit or ''] + [h['text'] for h in applicable]
        if any(re.search(r'10\s*\^\s*[+−-]?\d|10[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]', power_header(text))
               for text in unit_and_headers):
            skipped.append({'record_id': rid, 'reason': 'Explicit display multiplier requires its own reader'})
            continue
        lower, upper = row.get('value_min'), row.get('value_max')
        # Only remove a provably inconsistent interval. Do not create bounds
        # for unresolved or unparsed records, or change a correct scalar.
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                   for v in [lower, upper]) or (lower == literal and upper == literal):
            continue
        row['value_min'] = row['value_max'] = literal
        changes.append({'record_id': rid, 'kind': 'literal_scalar_bounds',
                        'before': [lower, upper], 'after': [literal, literal],
                        'cell_id': cell['cell_id'], 'source_cell': cell['text'],
                        'value_raw_preserved': True, 'units_preserved': True})
    return result, {'version': VERSION, 'changes': changes, 'skipped': skipped, 'gold_access': False}
