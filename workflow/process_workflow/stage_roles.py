"""Source-table roles with complete lineage; never infer actual specimen identity."""
import re
from copy import deepcopy

from .common import canonical
from .rules.headers import covers, norm_value
from .rules.qualifiers import plain


def _raw(value):
    return value.get('value_raw') if isinstance(value, dict) else value


def _source_cells(row, tables):
    result = []
    for patch in row['patches']:
        table = tables[patch['source_table_id']]
        found = [c for c in table.get('table_cells', []) if c['cell_id'] == patch['source_cell_id']]
        if len(found) == 1:
            result.append((patch['original_coordinate_index'], table, found[0], patch))
    return result


def _response_cell(owner, evidence, tables):
    """Locate the declared response source cell, without validating its value.

    The process context describes that source-table case only. A normalized
    property value (including uncertainty notation) is not a second source cell,
    nor does locating a cell certify the property value/unit/sample binding.
    """
    result = {}
    for eid in owner.get('evidence_ids', []):
        ev = evidence.get(eid, {})
        loc = ev.get('table_locator') or {}
        table = tables.get(loc.get('table_id'))
        if table is None:
            continue
        found = [c for c in table.get('table_cells', []) if c['cell_id'] == loc.get('cell_id')]
        if len(found) != 1:
            continue
        cell = found[0]
        if norm_value(ev.get('source_sentence')) != norm_value(cell['text']):
            continue
        result[(table['block_id'], cell['cell_id'])] = (table, cell)
    return next(iter(result.values())) if len(result) == 1 else None


def _alias_matches(alias, coordinate_indices, values):
    if alias is None:
        return False
    raw = _raw(alias)
    parts = [norm_value(x) for x in str(raw).split('|')]
    expected = [norm_value(x) for x in values]
    exact = parts == expected
    if isinstance(alias, dict):
        indices = set(alias.get('coordinate_indices', []))
        exact = exact or bool(indices and indices <= set(coordinate_indices) and len(parts) == 1 and parts[0] in expected)
    return exact


def _relocate_alias(row, context, coordinate_indices, values, counts, rule):
    other = (row.get('effective_measurement_context') or {}).get('other_conditions') or {}
    alias = other.get('source_condition_state')
    if not _alias_matches(alias, coordinate_indices, values):
        return
    context['original_condition_alias_relocated_from_measurement_context'] = deepcopy(alias)
    del other['source_condition_state']
    row['revision_map'].append(dict(rule=rule, field='source_condition_state', original=alias,
        original_value_sha256=canonical(alias), assertion_preserved_in_typed_context=True))
    counts['condition_aliases_relocated_to_source_stage'] += 1


def separate_preparation(row, tables, counts):
    sources = _source_cells(row, tables)
    coords = row['effective_coordinates']
    groups = {}
    for index, table, cell, patch in sources:
        caption = table.get('caption', '')
        if not re.search(r'\b(?:synthes(?:is|es)|preparation|polymerization|polycondensation)\b', caption, re.I):
            continue
        name = plain(coords[index].get('name_raw', '')).casefold()
        if re.search(r'\b(?:solvent|reagent|reactant)\b', name):
            groups.setdefault(table['block_id'], []).append((index, table, cell, patch))
    contexts = []
    for tid, quantities in groups.items():
        identities = [(i, table, cell) for i, table, cell, patch in sources if table['block_id'] == tid
            and re.search(r'\b(?:polymer|sample|material|code|entry)\b', plain(coords[i].get('name_raw', '')).casefold())]
        if not identities:
            continue
        intervals = [set(range(cell['row_index'], cell['row_index'] + int(cell.get('row_span', 1))))
            for i, table, cell, patch in quantities]
        intervals += [set(range(cell['row_index'], cell['row_index'] + int(cell.get('row_span', 1))))
            for i, table, cell in identities]
        shared = set.intersection(*intervals)
        if not shared:
            continue
        context = dict(scope='material_preparation_in_original_source_table', source_table_id=tid,
            source_table_sha256=canonical(tables[tid]), source_table_caption=tables[tid].get('caption'),
            source_case_rows=sorted(shared),
            author_sample_labels=[dict(coordinate_index=i, value_raw=coords[i].get('value_raw'),
                name_raw=coords[i].get('name_raw')) for i, t, c in identities],
            parameters=[dict(coordinate_index=i, name_raw=coords[i].get('name_raw'),
                value_raw=coords[i].get('value_raw'), unit_raw=coords[i].get('unit_raw'),
                source_table_id=tid, source_cell_id=cell['cell_id']) for i, t, cell, p in quantities],
            canonical_sample_id_or_physical_batch_not_inferred=True,
            all_original_sample_labels_and_quantity_qualifiers_required=True,
            complete_source_semantics_not_automatically_certified=True)
        contexts.append(context)
    if contexts:
        alias = ((row.get('effective_measurement_context') or {}).get('other_conditions') or {}).get('source_condition_state')
        matching = [context for context in contexts if _alias_matches(alias,
            [p['coordinate_index'] for p in context['parameters']],
            [p['value_raw'] for p in context['parameters']])]
        if len(matching) == 1:
            context = matching[0]
            _relocate_alias(row, context, [p['coordinate_index'] for p in context['parameters']],
                [p['value_raw'] for p in context['parameters']], counts, 'source_preparation_stage_alias')
        row['material_preparation_contexts'] = contexts
        counts['source_preparation_contexts'] += len(contexts)


def annotate_response_and_formulation(row, owner, evidence, tables, counts):
    located = _response_cell(owner, evidence, tables)
    if located is None:
        return
    table, response = located
    sources = [x for x in _source_cells(row, tables) if x[1]['block_id'] == table['block_id']]
    if not sources or any(not covers(cell, response['row_index'], cell['column_index']) for i, t, cell, p in sources):
        return
    # Require every coordinate to have a unique source cell in this same row.
    if {i for i, t, c, p in sources} != set(range(len(row['effective_coordinates']))):
        return
    headers = [c for c in table.get('table_cells', []) if c['row_index'] < response['row_index']
        and c['row_index'] < 2 and covers(c, c['row_index'], response['column_index'])]
    literal = ' | '.join(dict.fromkeys(c['text'] for c in sorted(headers, key=lambda c: c['row_index'])))
    calculated = bool(re.search(r'\bcalculated\b|\btheoretical\b|\(\s*cal\s*\)', literal, re.I))
    if calculated:
        # A calculated response is not an additional preparation or phase state.
        # Keep any old physical assertion active for source conflict review.
        row['analytical_model_contexts'] = [dict(source_table_id=table['block_id'], source_row=response['row_index'],
            response_cell_id=response['cell_id'], response_header_literal=literal,
            scope='source_explicitly_calculated_response',
            numerical_property_value_unit_and_binding_not_certified=True,
            no_new_prepared_specimen_or_physical_state_asserted=True,
            original_physical_context_if_any_not_silently_discarded=True)]
        counts['explicit_calculated_response_contexts'] += 1
        return
    family = re.search(r'\bof\s+([A-Za-z][A-Za-z0-9_-]*(?:/[A-Za-z][A-Za-z0-9_-]*){1,4})\s+(?:blends|composites)\b',
        table.get('caption', ''), re.I)
    if not family or len(sources) != 1:
        return
    index, _, dose, patch = sources[0]
    top = [c for c in table.get('table_cells', []) if c['row_index'] == 0 and covers(c, 0, dose['column_index'])]
    if len(top) != 1 or response['column_index'] == dose['column_index']:
        return
    content = re.fullmatch(r'([A-Za-z][A-Za-z0-9_-]*)\s+content\s*\(\s*phr\s*\)', top[0]['text'], re.I)
    if not content or content[1].casefold() not in {s.casefold() for s in family[1].split('/')}:
        return
    if not re.fullmatch(r'\d+(?:\.\d+)?', dose['text']):
        return
    context = dict(kind='reported_blend_formulation', source_table_id=table['block_id'],
        source_table_sha256=canonical(table), source_data_row=response['row_index'],
        material_family_literal=family[1], varied_component=content[1],
        preparation_stage='reported_blend_formulation_case_before_assay',
        dose=dict(role='reported_formulation_content', component=content[1], value_raw=dose['text'],
            unit_raw='phr', source_header_literal=top[0]['text'],
            percent_or_resin_mass_basis_conversion_not_inferred=True),
        response_cell_id=response['cell_id'], response_header_literal=literal,
        zero_dose_control_no_component_presence_or_addition_inferred=float(dose['text']) == 0,
        repeated_response_rows_not_additional_preparation_batches=True,
        source_condition_class_not_unique_physical_batch=True,
        original_property_binding_not_newly_certified=True)
    context['numerical_property_value_and_unit_not_validated_by_source_cell_location'] = True
    _relocate_alias(row, context, [index], [dose['text']], counts, 'source_formulation_stage_alias')
    row['material_source_grid_contexts'] = [context]
    counts['source_formulation_contexts'] += 1


def apply_stage_roles(row, owner, evidence, tables, counts):
    separate_preparation(row, tables, counts)
    annotate_response_and_formulation(row, owner, evidence, tables, counts)
