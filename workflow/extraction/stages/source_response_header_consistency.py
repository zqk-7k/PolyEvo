"""Distinguish response headers from full-width specimen section labels.

This repair never changes a numerical value, unit, sample identity or method.
It corrects source-derived context emitted by an earlier header reader.
"""
import copy
import re
from stages.stage4_direct_table_supplement import plain, table_cell_scalar, header_applies, evidence

VERSION = '1.0.0'


def response_headers(table, response):
    cells = table.get('table_cells', [])
    width = max((c['column_index'] + c.get('column_span', 1) for c in cells), default=0)
    # Use measurements across the table, not just this response column. A
    # calculated elemental row can be blank in the molecular-weight columns.
    data_rows = [c['row_index'] for c in cells if c['column_index'] > 0
                 and table_cell_scalar(c.get('text', '')) is not None
                 and not re.search(r'10\s*\^|10[⁰¹²³⁴⁵⁶⁷⁸⁹]', plain(c.get('text', '')))]
    boundary = min(data_rows) if data_rows else response['row_index']
    full_width = lambda c: c['row_index'] > 0 and c['column_index'] == 0 and c.get('column_span', 1) >= width
    headers = [c for c in cells if c['row_index'] < boundary and header_applies(c, response)
               and plain(c.get('text')) and not full_width(c)
               and not re.fullmatch(r'homopolymers?|copolymers?|blends?|ipns?', plain(c['text']), re.I)]
    groups = [c for c in cells if full_width(c) and c['row_index'] <= response['row_index']
              and plain(c.get('text'))]
    group = max(groups, key=lambda c: c['row_index']) if groups else None
    return headers, group


def repair_header_contexts(stage4, stage0):
    fixed = copy.deepcopy(stage4)
    tables = {t['block_id']: t for t in stage0['elements'] if t['type'] == 'table'}
    rows = [(r, r['property_id']) for r in fixed.get('properties', [])]
    rows += [(p, s['series_id'] + ':' + p['point_id'])
             for s in fixed.get('property_series', []) for p in s['points']]
    rows += [(r, r['specialized_id']) for r in fixed.get('specialized_property_observations', [])]
    changes = []
    for row, rid in rows:
        context = row.get('measurement_context') or {}
        conditions = context.get('other_conditions') or {}
        keys = [k for k in ('source_response_header', 'full_source_column_header_path') if conditions.get(k)]
        if not keys:
            continue
        candidates = {}
        for proof in row.get('evidence', []):
            table = tables.get(proof.get('block_id'))
            locator = proof.get('table_locator') or {}
            if not table or not locator.get('cell_id'):
                continue
            cell = next((c for c in table.get('table_cells', []) if c['cell_id'] == locator['cell_id']), None)
            if cell is not None and table_cell_scalar(cell.get('text')) is not None:
                candidates[(table['block_id'], cell['cell_id'])] = table, cell
        if len(candidates) != 1:
            continue
        table, cell = next(iter(candidates.values()))
        headers, group = response_headers(table, cell)
        if not headers or group is None:
            # Only migrate a positively identified full-width specimen group
            # that the historical parser confused with a response header.
            continue
        group_label = plain(group['text'])
        width = max(c['column_index'] + c.get('column_span', 1) for c in table['table_cells'])
        labels = [plain(c['text']) for c in table['table_cells'] if c['row_index'] > 0
                  and c['column_index'] == 0 and c.get('column_span', 1) >= width and plain(c.get('text'))]
        if not any(label in plain(conditions[k]) for label in labels for k in keys):
            continue
        point_changes = []
        header_proof = [evidence({'table_id': table['block_id'], 'page': table['page'], 'bbox': table.get('bbox')},
                                h, row_label='response header', column_label=h['text']) for h in headers]
        for key in keys:
            # A different previous group's name can occur above the first data
            # row; reconstruct the literal header, not a string subtraction.
            previous = conditions[key]
            corrected = ' | '.join(dict.fromkeys(plain(h['text']) for h in headers))
            if corrected == previous:
                continue
            conditions[key] = corrected
            context.setdefault('other_condition_evidence', {})[key] = copy.deepcopy(header_proof)
            point_changes.append({'field': key, 'before': previous, 'after': corrected})
        if point_changes:
            conditions['source_row_group_label'] = group_label
            context.setdefault('other_condition_evidence', {})['source_row_group_label'] = [
                evidence({'table_id': table['block_id'], 'page': table['page'], 'bbox': table.get('bbox')},
                         group, row_label=group_label, column_label='specimen section')]
            changes.append({'record_id': rid, 'changes': point_changes,
                            'source_specimen_section': group_label,
                            'actual_cell_id': cell['cell_id'], 'source_proof': header_proof})
    return fixed, {'version': VERSION, 'changes': changes, 'reference_answers_loaded': False,
                   'values_units_samples_methods_changed': False}
