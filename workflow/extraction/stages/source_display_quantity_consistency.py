"""Represent an explicitly scaled source scalar coherently in native output.

The unchanged external quantity projection must not pair an unscaled literal
with a scaled upper bound. Original literals remain in evidence and context.
No reference, plausible polymer range or derived new property is used.
"""
import copy
import math
import re
from stages.source_display_scaling import scale_rule
from stages.source_response_header_consistency import response_headers
from stages.stage4_direct_table_supplement import table_cell_scalar, canonical_unit, plain, power_header, evidence
from stages.stage4t_table_property import _conductivity_display_scale, _reciprocal_ohm_cm_unit
from stages.source_verified_exponent_runs import verified_run_scales

VERSION = '1.0.2'


def _unit_identity(unit):
    # g^-1 and g-1 are two serializations of the same printed exponent,
    # not a dimensional conversion. Keep K/C and cal/J distinct.
    return re.sub(r'\^(?=[+-]?\d)', '', canonical_unit(unit) or '')


def repair_display_quantities(stage4, stage0):
    fixed = copy.deepcopy(stage4)
    tables = {t['block_id']: t for t in stage0['elements'] if t['type'] == 'table'}
    certified_runs = verified_run_scales(stage0)
    rows = [(r, r, r['property_id']) for r in fixed.get('properties', [])]
    rows += [(p, s, s['series_id'] + ':' + p['point_id'])
             for s in fixed.get('property_series', []) for p in s['points']]
    rows += [(r, r, r['specialized_id']) for r in fixed.get('specialized_property_observations', [])]
    changes, skipped = [], []
    for row, parent, rid in rows:
        raw_unit = row.get('unit_raw') or parent.get('unit_raw')
        normalized = row.get('unit_normalized') or parent.get('unit_normalized') or raw_unit
        if not raw_unit or not normalized:
            continue
        # Already carrying a display multiplier in the emitted source unit is
        # a different coherent representation; never multiply it again.
        if any(re.search(r'10\s*\^|10[⁰¹²³⁴⁵⁶⁷⁸⁹]', power_header(u)) for u in (raw_unit, normalized)):
            continue
        inverse_ohm_equivalent = (_reciprocal_ohm_cm_unit(raw_unit) and canonical_unit(normalized) == 'S/cm')
        if _unit_identity(raw_unit) != _unit_identity(normalized) and not inverse_ohm_equivalent:
            continue
        candidates = {}
        for proof in row.get('evidence', []):
            table = tables.get(proof.get('block_id'))
            locator = proof.get('table_locator') or {}
            if not table or not locator.get('cell_id'):
                continue
            cell = next((c for c in table.get('table_cells', []) if c['cell_id'] == locator['cell_id']), None)
            raw_scalar = table_cell_scalar(row.get('value_raw', ''))
            original_literal = ((row.get('measurement_context') or {}).get('other_conditions') or {}).get('source_display_original_cell')
            # Added header proofs are evidence too, but are not additional
            # response cells. Keep only the row's numerical/literal witness.
            literal_matches = (cell is not None and
                (table_cell_scalar(cell['text']) == raw_scalar and raw_scalar is not None
                 or original_literal is not None and plain(cell['text']) == plain(original_literal)))
            if cell and literal_matches:
                candidates[(table['block_id'], cell['cell_id'])] = table, cell
        if len(candidates) != 1:
            continue
        table, cell = next(iter(candidates.values()))
        source_text = plain(cell['text'])
        if re.search(r'±|\\pm|[<>≤≥≈~]|\\sim|\\approx', source_text):
            continue
        source_scalar = table_cell_scalar(cell['text'])
        if source_scalar is None:
            continue
        headers, _ = response_headers(table, cell)
        rules = [(scale_rule(h['text']), h) for h in headers]
        rules = [(rule, h) for rule, h in rules if rule]
        name = ' '.join(str(row.get(k) or parent.get(k) or '')
                        for k in ('property_name_raw', 'property_name_normalized', 'semantic_label'))
        if re.search(r'conductivity|conductance|σ|\\sigma', name, re.I):
            for header in headers:
                display = _conductivity_display_scale(header['text'])
                if display:
                    rules.append(((display['value_scale_factor'], display['scale_interpretation']), header))
        certified = certified_runs.get(cell['cell_id'])
        if certified:
            reset = next((c for c in table.get('table_cells', [])
                          if c['cell_id'] == certified['reset_cell_id']), None)
            if reset:
                rules.append(((certified['factor'],
                    'PDF-verified shared exponent; reread printed reset cell'), reset))
        if not rules:
            continue
        factors = {rule[0] for rule, _ in rules}
        if len(factors) != 1:
            skipped.append({'record_id': rid, 'reason': 'Conflicting explicit source scales'})
            continue
        factor = next(iter(factors))
        expected = source_scalar * factor
        if not math.isfinite(expected):
            continue
        raw_number = table_cell_scalar(row.get('value_raw', ''))
        current = (raw_number, row.get('value_min'), row.get('value_max'))
        if all(isinstance(v, (int, float)) and not isinstance(v, bool)
               and math.isclose(v, expected, rel_tol=1e-12, abs_tol=0.) for v in current):
            continue
        before = {k: row.get(k) for k in ('value_raw', 'value_min', 'value_max', 'unit_raw', 'unit_normalized')}
        row['value_raw'] = format(expected, '.12g')
        row['value_min'] = row['value_max'] = expected
        context = row.setdefault('measurement_context', {})
        context['condition_status'] = 'reported'
        context.setdefault('other_conditions', {}).update(
            source_display_original_cell=cell['text'], source_display_scale_factor=str(factor),
            source_display_scale_basis=rules[0][0][1],
            source_display_header=' | '.join(h['text'] for _, h in rules),
            quantity_representation='physical scalar; original printed cell retained in evidence and context')
        if certified:
            context['other_conditions'].update(
                source_exponent_run_reset_cell=certified['reset_cell_id'],
                source_exponent_run_pdf_review_sha256=certified['review_sha256'])
        proofs = [evidence({'table_id': table['block_id'], 'page': table['page'], 'bbox': table.get('bbox')},
                          h, row_label='display convention', column_label=h['text']) for _, h in rules]
        for proof in proofs:
            if proof not in row['evidence']:
                row['evidence'].append(proof)
        changes.append({'record_id': rid, 'before': before,
                        'after': {k: row.get(k) for k in before}, 'source_cell_id': cell['cell_id'],
                        'source_original_cell': cell['text'], 'factor': factor, 'source_proof': proofs})
    return fixed, {'version': VERSION, 'changes': changes, 'skipped': skipped,
                   'reference_answers_loaded': False, 'new_measurements_created': False}
