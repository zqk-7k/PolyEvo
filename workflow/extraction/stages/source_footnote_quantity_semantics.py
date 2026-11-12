"""Use a witnessed, own-table footnote definition for viscosity taxonomy."""
import copy
import math
import re
from stages.source_table_relations import witness
from stages.source_response_header_consistency import response_headers
from stages.stage4_direct_table_supplement import plain, table_cell_scalar
from stages.table_grid import parse_table_cells

VERSION = '1.0.0'
KINDS = ('inherent', 'intrinsic', 'reduced', 'specific')


def repair(stage4, stage0):
    result = copy.deepcopy(stage4); changes = []; grids = {}
    blocks = {b['block_id']: b for b in stage0['elements']}

    def definition(row, parent):
        current = row.get('property_name_normalized') or parent.get('property_name_normalized') or ''
        if current not in {k+'_viscosity' for k in KINDS}: return None
        value = table_cell_scalar(row.get('value_raw', ''))
        if value is None: return None
        if any(row.get(k) is not None and not math.isclose(float(row[k]), value, abs_tol=1e-9)
               for k in ('value_min', 'value_max')): return None
        locations = {}
        for proof in row.get('evidence', []):
            block = blocks.get(proof.get('block_id'), {})
            loc = proof.get('table_locator') or {}
            if block.get('type') != 'table': continue
            cell = next((c for c in block.get('table_cells', []) if c['cell_id'] == loc.get('cell_id')), None)
            scalar = table_cell_scalar((cell or {}).get('text', ''))
            if scalar is not None and math.isclose(scalar, value, abs_tol=1e-9):
                locations[(block['block_id'], cell['cell_id'])] = (block, cell)
        if len(locations) != 1: return None
        table, cell = next(iter(locations.values()))
        body = table.get('table_body') or table.get('text') or ''
        if '<table' not in body.lower(): return None
        if table['block_id'] not in grids:
            grids[table['block_id']] = {c.cell_id: c.model_dump() for c in parse_table_cells(body, table['block_id'])}
        grid = grids[table['block_id']]
        headers, _ = response_headers(table, cell)
        if grid.get(cell['cell_id'], {}).get('text') != cell['text'] or not headers: return None
        if any(grid.get(h['cell_id'], {}).get('text') != h['text'] for h in headers): return None
        header = ' | '.join(dict.fromkeys(h['text'].strip() for h in headers))
        if not re.search(r'\bIV\b|viscos|\\eta|η', plain(header), re.I): return None
        found = []
        for context in (row.get('measurement_context') or {}, parent.get('measurement_context') or {}):
            hints = context.get('other_condition_evidence', {})
            for key in ('source_method', 'method', 'measurement_method'):
                for evidence in hints.get(key, []):
                    block = blocks.get(evidence.get('block_id'), {})
                    if block.get('type') != 'footnote' or (block.get('content') or {}).get('owning_table_block_id') != table['block_id']:
                        continue
                    quote = evidence.get('source_sentence') or ''
                    proof = witness({'block_id': block['block_id'], 'quote': quote}, blocks)
                    kinds = [k for k in KINDS if re.search(r'\b'+k+r'\s+viscosity\b', quote, re.I)]
                    if proof and len(kinds) == 1: found.append((kinds[0]+'_viscosity', proof))
        if not found or len({k for k, _ in found}) != 1 or found[0][0] == current: return None
        return current, found[0][0], found[0][1], header

    targets = [(r, {}, r['property_id']) for r in result.get('properties', [])]
    for series in result.get('property_series', []):
        targets.extend((p, series, series['series_id']+':'+p['point_id']) for p in series['points'])
    by_series = {}
    for row, parent, rid in targets:
        match = definition(row, parent)
        if not match: continue
        before, after, proof, header = match
        row['property_name_normalized'] = after
        raw = row.get('property_name_raw') or parent.get('property_name_raw', '')
        wrong = before.replace('_', ' ')
        if wrong in raw.lower(): row['property_name_raw'] = header
        if proof not in row['evidence']: row['evidence'].append(proof)
        if parent: by_series.setdefault(parent['series_id'], []).append((rid, after, proof, header))
        changes.append({'record_id': rid, 'before': before, 'after': after,
                        'source_header': header, 'own_table_definition': proof})
    for series in result.get('property_series', []):
        fixed = by_series.get(series['series_id'], [])
        if fixed and len(fixed) == len(series['points']) and len({c[1] for c in fixed}) == 1:
            old = series.get('property_name_normalized', '')
            series['property_name_normalized'] = fixed[0][1]
            if old.replace('_', ' ') in series.get('property_name_raw', '').lower():
                series['property_name_raw'] = fixed[0][3]
            if fixed[0][2] not in series['evidence']: series['evidence'].append(fixed[0][2])
    return result, {'version': VERSION, 'changes': changes, 'reference_answers_loaded': False,
                    'values_units_samples_and_methods_changed': False}

