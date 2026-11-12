"""Repair response headers used as methods, with table-linked source evidence.

No evaluation answers are accepted. A technique must be explicit both in the
table caption and in a source paragraph naming that printed table. Merely seeing
a Tg, modulus or molecular-weight response never implies a technique.
"""
import copy
import math
import re

from stages.table_grid import parse_table_cells
from stages.source_response_header_consistency import response_headers
from stages.source_table_relations import norm, witness
from stages.stage4_direct_table_supplement import table_cell_scalar

VERSION = '1.0.0'
TECHNIQUES = [
    (r'dynamic\s+mechanical', 'Dynamic mechanical analysis (DMA)'),
    (r'differential\s+scanning\s+calorimetr\w*|\bDSC\b', 'Differential scanning calorimetry (DSC)'),
    (r'gel\s+permeation\s+chromatograph\w*|\bGPC\b', 'Gel permeation chromatography (GPC)'),
    (r'thermogravimetric\s+analys\w*|\bTGA\b', 'Thermogravimetric analysis (TGA)'),
]


def explicit_method(table, blocks):
    caption = table.get('caption') or ''
    number = re.search(r'\bTable\s+(\d+)\b', caption, re.I)
    methods = [(pat, label) for pat, label in TECHNIQUES if re.search(pat, caption, re.I)]
    if not number or len(methods) != 1:
        return None
    pattern, label = methods[0]
    for block in blocks.values():
        text = block.get('text') or ''
        if block.get('type') == 'table':
            continue
        if re.search(r'\bTable\s+' + number[1] + r'\b', text, re.I) and re.search(pattern, text, re.I):
            proof = witness({'block_id': block['block_id'], 'quote': text}, blocks)
            if proof:
                return label, proof
    return None


def repair(stage4, stage0):
    result = copy.deepcopy(stage4)
    blocks = {b['block_id']: b for b in stage0['elements']}
    grids = {}
    changes = []

    def check(row, parent):
        current = row.get('determination_method_raw') or parent.get('determination_method_raw')
        if not current or any(re.search(pat, current, re.I) for pat, _ in TECHNIQUES):
            return None
        value = table_cell_scalar(row.get('value_raw', ''))
        if value is None:
            return None
        for k in ('value_min', 'value_max'):
            if row.get(k) is not None and not math.isclose(float(row[k]), value, abs_tol=1e-9):
                return None
        locations = {}
        for proof in row.get('evidence', []):
            table = blocks.get(proof.get('block_id'), {})
            locator = proof.get('table_locator') or {}
            if table.get('type') != 'table':
                continue
            cell = next((c for c in table.get('table_cells', []) if c['cell_id'] == locator.get('cell_id')), None)
            scalar = table_cell_scalar((cell or {}).get('text', ''))
            if scalar is not None and math.isclose(scalar, value, abs_tol=1e-9):
                locations[(table['block_id'], cell['cell_id'])] = (table, cell)
        if len(locations) != 1:
            return None
        table, cell = next(iter(locations.values()))
        body = table.get('table_body') or table.get('text') or ''
        if '<table' not in body.lower():
            return None
        if table['block_id'] not in grids:
            grids[table['block_id']] = {c.cell_id: c.model_dump() for c in parse_table_cells(body, table['block_id'])}
        grid = grids[table['block_id']]
        if grid.get(cell['cell_id'], {}).get('text') != cell['text']:
            return None
        headers, _ = response_headers(table, cell)
        if not headers or any(grid.get(h['cell_id'], {}).get('text') != h['text'] for h in headers):
            return None
        if norm(current) not in {norm(h['text']) for h in headers}:
            return None
        verified = explicit_method(table, blocks)
        return (current, *verified, table['block_id']) if verified else None

    targets = [(r, {}, r['property_id']) for r in result.get('properties', [])]
    targets += [(r, {}, r.get('property_id') or r.get('specialized_id')) for r in result.get('specialized_properties', [])]
    for series in result.get('property_series', []):
        targets += [(p, series, series['series_id'] + ':' + p['point_id']) for p in series['points']]
    changed_points = {}
    for row, parent, rid in targets:
        answer = check(row, parent)
        if not answer:
            continue
        old, method, proof, table_id = answer
        row['determination_method_raw'] = method
        context = row.setdefault('measurement_context', {})
        context.setdefault('other_conditions', {})['method'] = method
        context.setdefault('other_condition_evidence', {})['method'] = [proof]
        context.setdefault('other_condition_evidence_ids', {}).pop('method', None)
        context['condition_status'] = 'reported'
        if proof not in row['evidence']:
            row['evidence'].append(proof)
        if parent:
            changed_points.setdefault(parent['series_id'], []).append((row['point_id'], method, proof))
        changes.append({'record_id': rid, 'before_method': old, 'after_method': method,
                        'table_id': table_id, 'method_evidence': proof})
    for series in result.get('property_series', []):
        repaired = changed_points.get(series['series_id'], [])
        if repaired and len(repaired) == len(series['points']) and len({r[1] for r in repaired}) == 1:
            # Replace a proven wrong common header, rather than retaining a
            # contradictory common method behind correct point-local methods.
            series['determination_method_raw'] = repaired[0][1]
            context = series.setdefault('measurement_context', {})
            context.setdefault('other_conditions', {})['method'] = repaired[0][1]
            context.setdefault('other_condition_evidence', {})['method'] = [repaired[0][2]]
            context.setdefault('other_condition_evidence_ids', {}).pop('method', None)
            context['condition_status'] = 'reported'
            if repaired[0][2] not in series['evidence']:
                series['evidence'].append(repaired[0][2])
    return result, {'version': VERSION, 'changes': changes, 'reference_answers_loaded': False,
                    'values_units_samples_and_processes_changed': False}


