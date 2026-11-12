"""Keep a recovered response's context aligned with its verified source column.

The guarded Stage4T PMT/viscosity mapping is re-executed from the complete
native table. No new quantity, method or specimen is inferred here.
"""
import copy
import math
from schema.polymer_schema import Stage0Document
from stages.stage4t_table_property import shadow_extract_table
from stages.table_grid import table_cells_for, parse_table_cells
from stages.stage4_direct_table_supplement import evidence, plain, scalar

VERSION = '1.0.1'


def repair(stage4, stage0):
    result = copy.deepcopy(stage4); changes = []; tables = {}
    for element in Stage0Document.model_validate(stage0).elements:
        if element.type != 'table': continue
        # Cached cell locators must agree with the current original table, not
        # merely with an earlier OCR grid that happened to share cell IDs.
        body = element.table_body or element.text or ''
        if '<table' not in body.lower(): continue
        original = [c.model_dump(mode='json') for c in parse_table_cells(body, element.block_id)]
        cached = [c.model_dump(mode='json') for c in table_cells_for(element)]
        fields = ('cell_id','row_index','column_index','row_span','column_span','text')
        signature = lambda grid: [{k: c.get(k) for k in fields} for c in grid]
        if signature(original) != signature(cached): continue
        shadow = shadow_extract_table(element)
        candidates = {o['cell_id']: o for o in shadow['observations']
            if o.get('alignment_status') == 'paired_right_shift'
            and o.get('property_name_normalized') == 'melting_temperature'}
        if candidates:
            cells = [c.model_dump(mode='json') for c in table_cells_for(element)]
            tables[element.block_id] = (element, candidates, cells, set(shadow['header_rows']))
    targets = [(r, {}, r['property_id']) for r in result.get('properties', [])]
    for series in result.get('property_series', []):
        targets.extend((p, series, series['series_id']+':'+p['point_id']) for p in series['points'])
    for row, parent, rid in targets:
        context = row.get('measurement_context') or {}
        conditions = context.get('other_conditions') or {}
        old = conditions.get('source_response_header')
        if not old or conditions.get('alignment_status') != 'paired_right_shift': continue
        prop = row.get('property_name_normalized') or parent.get('property_name_normalized', '')
        if prop not in {'melting_temperature', 'polymer melting temperature', 'polymer_melt_temperature'}: continue
        if (row.get('unit_normalized') or parent.get('unit_normalized')) != '°C': continue
        value = scalar(row.get('value_raw', ''))
        if value is None or any(row.get(k) is not None and not math.isclose(float(row[k]), value, abs_tol=1e-9)
                                for k in ('value_min', 'value_max')): continue
        locations = {}
        for proof in row.get('evidence', []):
            table_id = proof.get('block_id'); locator = proof.get('table_locator') or {}
            if table_id not in tables: continue
            element, candidates, cells, header_rows = tables[table_id]
            aligned = candidates.get(locator.get('cell_id'))
            cell = next((c for c in cells if c['cell_id'] == locator.get('cell_id')), None)
            if aligned is None or cell is None or scalar(cell['text']) != value: continue
            headers = [c for c in cells if c['row_index'] in header_rows
                and c['column_index'] == aligned['header_column_index'] and 'PMT' in plain(c['text'])]
            if len(headers) == 1: locations[(table_id, cell['cell_id'])] = (element, headers[0], cell)
        if len(locations) != 1: continue
        element, header, cell = next(iter(locations.values()))
        corrected = plain(header['text'])
        if plain(old) == corrected: continue
        # A previously appended header claim must be traceable to this table.
        previous = context.get('other_condition_evidence', {}).get('source_response_header', [])
        if not previous or any(p.get('block_id') != element.block_id for p in previous): continue
        proof = evidence({'table_id': element.block_id, 'page': element.page, 'bbox': element.bbox},
                         header, row_label='response header', column_label=header['text'])
        conditions['source_response_header'] = corrected
        context.setdefault('other_condition_evidence', {})['source_response_header'] = [proof]
        context.setdefault('other_condition_evidence_ids', {}).pop('source_response_header', None)
        changes.append({'record_id': rid, 'before': old, 'after': corrected,
            'source_response_cell': cell['cell_id'], 'source_header_proof': proof,
            'reexecuted_alignment': 'guarded Stage4T paired_right_shift'})
    return result, {'version': VERSION, 'changes': changes,
        'reference_answers_loaded': False, 'values_units_samples_methods_processes_changed': False}
