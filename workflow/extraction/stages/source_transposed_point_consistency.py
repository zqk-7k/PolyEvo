"""Do not inherit a neighboring response's units or dynamic scan qualifiers.

Only an already source-declared kinetic row and its existing common definition
are used. No physical unit for an unlabelled kinetic constant is invented.
"""
import copy
import re
from stages.source_table_relations import norm, witness
from stages.stage4_direct_table_supplement import plain
from stages.table_grid import parse_table_cells

VERSION = '1.0.1'


def repair(stage4, stage0):
    out = copy.deepcopy(stage4)
    blocks = {b['block_id']: b for b in stage0['elements']}
    changes = []
    for series in out.get('property_series', []):
        parent = series.get('measurement_context') or {}
        own_header = (parent.get('other_conditions') or {}).get('source_property_header')
        method = series.get('determination_method_raw') or ''
        if not own_header or not re.search(r'\bisothermal\b', method, re.I):
            continue
        for point in series.get('points', []):
            context = point.get('measurement_context') or {}
            other = context.get('other_conditions') or {}
            if norm(other.get('source_property_header', '')) != norm(own_header):
                continue
            located = []
            for proof in point.get('evidence', []):
                block = blocks.get(proof.get('block_id'), {})
                if block.get('type') != 'table':
                    continue
                cell = next((c for c in block.get('table_cells', []) if c['cell_id'] ==
                             (proof.get('table_locator') or {}).get('cell_id')), None)
                if not cell:
                    continue
                row_label = [c for c in block.get('table_cells', []) if c['row_index'] == cell['row_index']
                             and c['column_index'] == 0 and c['column_index'] < cell['column_index']]
                if len(row_label) != 1 or norm(row_label[0]['text']) != norm(own_header):
                    continue
                body = block.get('table_body') or block.get('text') or ''
                if '<table' not in body.lower():
                    continue
                grid = {c.cell_id:c.model_dump() for c in parse_table_cells(body, block['block_id'])}
                if grid.get(cell['cell_id'], {}).get('text') == cell['text'] and grid.get(row_label[0]['cell_id'], {}).get('text') == row_label[0]['text']:
                    located.append((block, cell, row_label[0]))
            if len(located) != 1:
                continue
            before = copy.deepcopy(point)
            block, cell, row_label = located[0]
            raw_name = series.get('property_name_normalized') or series.get('property_name_raw') or ''
            kinetic = bool(re.search(r'Avrami\s+(?:exponent|crystallization\s+rate\s+constant)', raw_name, re.I))
            label = re.sub(r'[\s_${}\\]', '', plain(row_label['text'])).casefold()
            # Preserve the parent's faithful absence of a printed unit. Seconds
            # or Celsius from a different property row are not a valid override.
            if kinetic and label in {'n', 'kn'} and not series.get('unit_raw') and not series.get('unit_normalized'):
                if point.get('unit_raw') == point.get('unit_normalized') and point.get('unit_raw') in {'s', '°C', 'C', 'K'}:
                    point['unit_raw'] = None
                    point['unit_normalized'] = None
            hints = context.get('other_condition_evidence') or {}
            if re.search(r'\bdynamic\b', other.get('source_method', ''), re.I):
                witnesses = hints.get('source_method') or []
                verified_witnesses = [p for p in witnesses if witness(
                    {'block_id':p.get('block_id'),'quote':p.get('source_sentence','')}, blocks)]
                parent_witnesses = (parent.get('other_condition_evidence') or {}).get('source_method', [])
                parent_verified = bool(parent_witnesses) and all(witness(
                    {'block_id':p.get('block_id'),'quote':p.get('source_sentence','')}, blocks)
                    for p in parent_witnesses)
                parent_source = ' '.join((blocks.get(p.get('block_id'),{}).get('text') or '')
                                         for p in parent_witnesses)
                parent_verified = parent_verified and bool(re.search(r'\bisothermal\b',parent_source,re.I))
                wrong_row = any(p.get('block_id') == block['block_id'] and
                                norm(p.get('source_sentence', '')) != norm(own_header) and
                                re.search(r'T_?c|T\s*\{\s*c', plain(p.get('source_sentence', '')), re.I)
                                for p in verified_witnesses)
                cooling = any('cooling rate' in (p.get('source_sentence') or '').casefold()
                              for p in verified_witnesses)
                if wrong_row and cooling and parent_verified:
                    other['source_method'] = method
                    hints['source_method'] = copy.deepcopy((parent.get('other_condition_evidence') or {}).get('source_method', []))
                    if other.get('source_heating_rate') and any('cooling rate' in (p.get('source_sentence') or '').casefold() and witness(
                           {'block_id':p.get('block_id'),'quote':p.get('source_sentence','')},blocks)
                           for p in hints.get('source_heating_rate', [])):
                        other.pop('source_heating_rate')
                        hints.pop('source_heating_rate', None)
            if point != before:
                changes.append({'record_id':series['series_id']+':'+point['point_id'],
                                'before':before, 'own_response_cell':cell,
                                'own_response_header':row_label, 'existing_parent_method':method,
                                'unit_inferred':False})
    return out, {'version':VERSION,'changes':changes,'reference_answers_loaded':False,
                 'numeric_values_and_sample_bindings_unchanged':True,
                 'no_units_for_unlabelled_rate_constants_invented':True}
