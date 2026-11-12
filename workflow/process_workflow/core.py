"""Dataset-independent, deterministic recovery from source and native caches.

No gold, score, historical acceptance file, paper ID rule, or network input.
Source-location checks below are not semantic correctness certificates.
"""
import re
from collections import Counter
from copy import deepcopy

from . import VERSION
from .common import ROOTS, canonical, resolve, walk
from .rules import aliases, descriptions, headers, labelled, literal_headers
from .rules import named_units, nominal, qualifiers, subheaders
from .stage_roles import apply_stage_roles


def _cell_patch(table, cell, heading, index, original, evidence_id, locator):
    return dict(original_coordinate_index=index,
        original_coordinate_sha256=canonical(original), original_name_raw=original.get('name_raw'),
        restored_name_raw=' / '.join(h['text'] for h in heading),
        source_table_id=table['block_id'], source_table_sha256=canonical(table),
        source_cell_id=cell['cell_id'], source_cell_sha256=canonical(cell),
        original_header_cells=deepcopy(heading), source_evidence_id=evidence_id,
        requested_locator=deepcopy(locator), value_and_unit_preserved=True)


def _source_header(table, cell, locator):
    col = locator.get('column_index')
    if not isinstance(col, int):
        return None
    cells = table.get('table_cells', [])
    heading = headers.headers_for(table, cell, col)
    if not heading:
        found = [c for c in cells if c['row_index'] == 0
            and headers.covers(c, 0, col) and literal_headers.named_header(c.get('text', ''))]
        if len(found) != 1 or cell['row_index'] <= 0:
            return None
        heading = deepcopy(found)
    top = [c for c in cells if c['row_index'] == 0 and c['column_index'] > 0 and str(c.get('text', '')).strip()]
    # A run label is a column axis, not the parameter's name.
    if len(top) >= 2 and all(re.fullmatch(r'Run\s+\d+', str(c['text']).strip(), re.I) for c in top):
        left = [c for c in cells if headers.covers(c, cell['row_index'], 0) and str(c.get('text', '')).strip()]
        if len(left) == 1:
            return dict(name_raw=left[0]['text'], heading=deepcopy(heading),
                row_axis_cell=deepcopy(left[0]), author_run_axis_cells=deepcopy(heading))
    last = max(h['row_index'] for h in heading)
    added = []
    for row in range(last + 1, min(cell['row_index'], 3)):
        found = [c for c in cells if c['row_index'] == row and headers.covers(c, row, col)]
        if len(found) != 1:
            break
        value = found[0]
        short = subheaders.plausible_unit_or_named_subheader(value.get('text', ''))
        named = (int(cell.get('column_span', 1)) == 1
            and named_units.explicit_named_unit(value.get('text', '')))
        if not (short or named):
            break
        added.append(deepcopy(value))
    heading = deepcopy(heading) + added
    return dict(name_raw=' / '.join(h['text'] for h in heading), heading=heading)


def restore_coordinates(doc, stage0):
    tables = {x['block_id']: x for x in stage0.get('elements', []) if x.get('type') == 'table'}
    evidence = {e['evidence_id']: e for e in doc.get('evidence', []) if e.get('evidence_id')}
    rows = []
    counts = Counter()
    for root in ROOTS:
        for coords_path, coords, owner_path, owner in walk(doc.get(root, []), '/' + root):
            interpreted = deepcopy(coords)
            patches = []
            unresolved = []
            for i, co in enumerate(coords):
                candidates = {}
                for eid in co.get('evidence_ids', []):
                    loc = evidence.get(eid, {}).get('table_locator') or {}
                    table = tables.get(loc.get('table_id'))
                    if table is None:
                        continue
                    cell = headers.source_cell(table, loc, co.get('value_raw'))
                    if cell is None:
                        continue
                    found = _source_header(table, cell, loc)
                    if not found:
                        continue
                    patch = _cell_patch(table, cell, found['heading'], i, co, eid, loc)
                    patch['restored_name_raw'] = found['name_raw']
                    for field in ['row_axis_cell', 'author_run_axis_cells']:
                        if field in found:
                            patch[field] = found[field]
                    key = (table['block_id'], cell['cell_id'], found['name_raw'], canonical(found['heading']))
                    candidates[key] = patch
                if len(candidates) != 1:
                    unresolved.append(dict(index=i, reason='no_unique_source_cell_and_header',
                        source_candidate_count=len(candidates)))
                    continue
                patch = next(iter(candidates.values()))
                interpreted[i]['name_raw'] = patch['restored_name_raw']
                assert {k: v for k, v in interpreted[i].items() if k != 'name_raw'} == {
                    k: v for k, v in co.items() if k != 'name_raw'}
                patches.append(patch)
                counts['source_header_positions'] += 1
                counts['coordinate_names_changed'] += co.get('name_raw') != patch['restored_name_raw']
                counts['transposed_axis_positions'] += 'row_axis_cell' in patch
            rows.append(dict(owner_path=owner_path, original_owner_sha256=canonical(owner),
                original_coordinate_path=coords_path, original_coordinates_sha256=canonical(coords),
                effective_coordinates=interpreted,
                effective_measurement_context=deepcopy(owner.get('measurement_context')),
                patches=patches, unresolved_coordinates=unresolved, revision_map=[],
                existing_sample_id=owner.get('sample_id'), existing_sample_ids=deepcopy(owner.get('sample_ids')),
                existing_entity_id=owner.get('entity_id'),
                original_context_retained_in_immutable_property_source=True,
                canonical_property_binding_not_inferred=True,
                semantic_source_support='unreviewed'))
            counts['coordinate_owners'] += 1
            counts['original_coordinate_positions'] += len(coords)
            counts['unresolved_coordinate_positions'] += len(unresolved)
    return rows, counts


def apply_typed_scopes(row, tables, counts):
    context = row['effective_measurement_context']
    if not isinstance(context, dict) or not isinstance(context.get('other_conditions'), dict):
        return
    other = context['other_conditions']
    coords = row['effective_coordinates']
    patches = {p['original_coordinate_index']: p for p in row['patches']}
    ratios = {}
    for i, co in enumerate(coords):
        quantities = aliases.numeric_ratio(co.get('value_raw'))
        if quantities is None or i not in patches:
            continue
        patch = patches[i]
        names = aliases.pair(co.get('name_raw', ''))
        caption_names = aliases.pair(tables[patch['source_table_id']].get('caption', ''))
        if not names and str(co.get('name_raw', '')).strip().lower() in {'blend', 'modified blend', 'material', 'polymer'}:
            names = caption_names
        if len(names) != 1:
            continue
        names = next(iter(names))
        if caption_names and names not in caption_names:
            continue
        signature = (names, quantities, patch['source_table_id'], patch['source_cell_id'])
        ratios.setdefault(signature, []).append(i)
    row['explicit_component_ratio_contexts'] = [dict(component_names=list(names),
        ratio_values_literal=list(values), source_table_id=tid, source_cell_id=cid,
        coordinate_indices=indices, ratio_basis_unknown_not_inferred=True,
        canonical_sample_identity_not_inferred=True)
        for (names, values, tid, cid), indices in ratios.items()]
    counts['named_component_ratio_contexts'] += len(ratios)
    raw = other.get('source_condition_state')
    matching = {}
    if isinstance(raw, (str, int, float)):
        for i, co in enumerate(coords):
            if i not in patches or aliases.norm(co.get('value_raw')) != aliases.norm(raw):
                continue
            p = patches[i]
            key = canonical([co.get('name_raw'), co.get('value_raw'), co.get('unit_raw'), p['source_table_id'], p['source_cell_id']])
            matching.setdefault(key, []).append(i)
        if len(matching) == 1:
            indices = next(iter(matching.values()))
            co = coords[indices[0]]
            typed = dict(name_raw=co.get('name_raw'), value_raw=raw, unit_raw=co.get('unit_raw'),
                coordinate_indices=indices, role_source='same_owner_original_table_coordinate',
                no_value_or_unit_conversion=True)
            other['source_condition_state'] = typed
            row['revision_map'].append(dict(field='source_condition_state', original=raw,
                replacement_sha256=canonical(typed), rule='same_owner_source_typed_alias'))
            counts['same_owner_condition_aliases'] += 1
    phase = other.get('source_crystallization_state')
    if not isinstance(phase, str):
        return
    possibilities = {}
    for (names, values, tid, cid), indices in ratios.items():
        for index, component in enumerate(names):
            if re.match(r'^\s*' + re.escape(component) + r'\s+(?:(?:particles|droplets|phase|component)\s+)?(?:remained|remains|was|is)\b', phase, re.I):
                possibilities[(names, values, component)] = indices
    if len(possibilities) != 1:
        return
    (names, values, component), indices = next(iter(possibilities.items()))
    present = float(values[names.index(component)]) > 0
    scoped = dict(subject=component, scope='named_component_when_present', state_text=phase,
        component_names=list(names), ratio_values_literal=list(values),
        applicable_to_this_author_row=present, ratio_basis_unknown_not_inferred=True,
        applicability_reason='explicit_positive_component_ratio' if present else 'explicit_zero_component_ratio')
    other['source_crystallization_state'] = scoped
    row['revision_map'].append(dict(field='source_crystallization_state', original=phase,
        replacement_sha256=canonical(scoped), rule='named_component_presence_guard'))
    counts['component_phase_scopes'] += 1
    counts['zero_component_phase_guards'] += not present


def _anchors(evidence_ids, evidence, blocks):
    result = []
    missing = []
    for ident in evidence_ids:
        ev = evidence.get(ident)
        if ev is None or ev.get('block_id') not in blocks:
            missing.append(ident)
            continue
        block = blocks[ev['block_id']]
        result.append(dict(evidence_id=ident, evidence_sha256=canonical(ev),
            block_id=ev['block_id'], block_sha256=canonical(block), page=block.get('page')))
    return result, missing


def recover_descriptions(doc, blocks, evidence):
    active = []
    pending = []
    counts = Counter()
    for i, sample in enumerate(doc.get('samples', [])):
        text = sample.get('state_description')
        if not isinstance(text, str) or not text.strip():
            continue
        proposals = []
        for source, function in [('nominal_polymerization', nominal.propose), ('labelled_polymerization', labelled.propose)]:
            found = function(text, sample['sample_id'])
            if found is not None:
                proposals.append((source, found))
        if not proposals:
            proposals = [('explicit_verb_description', x) for x in descriptions.proposals(text, sample['sample_id'])]
        anchors, missing = _anchors(sample.get('evidence_ids', []), evidence, blocks)
        normalized = qualifiers.plain(text).casefold()
        exact_blocks = [a for a in anchors if normalized and normalized in qualifiers.plain(blocks[a['block_id']].get('text', '')).casefold()]
        single_action = len(list(descriptions.VERBS.finditer(text))) <= 1
        for kind, proposal in proposals:
            proposal = deepcopy(proposal)
            proposal.update(rule=kind, source_field_path=f'/samples/{i}/state_description',
                source_sample_sha256=canonical(sample), complete_original_description=text,
                source_anchors=anchors, missing_evidence_ids=missing,
                applicability='existing_declared_sample_only',
                input_and_intermediate_state_not_inferred=True,
                semantic_source_support='unreviewed', accepted_into_prediction=False)
            safe = bool(exact_blocks and not missing and single_action
                and not descriptions.NEGATION.search(text) and not descriptions.MEASUREMENT.search(text))
            if safe:
                proposal['accepted_into_prediction'] = True
                proposal['source_literal_alignment'] = exact_blocks
                proposal['rule_publication_basis'] = 'single_action_complete_native_description_aligned_to_source'
                active.append(proposal)
            else:
                proposal['pending_reason'] = 'complete_source_alignment_or_single_action_scope_not_established'
                pending.append(proposal)
            counts['description_candidates'] += 1
            counts['active_description_histories' if safe else 'pending_description_histories'] += 1
    return active, pending, counts


def native_graph(doc):
    """Expose declared native endpoints. No sample identity merging or array-order edges."""
    states = []
    operations = []
    parameters = []
    bindings = []
    samples = {s['sample_id']: s for s in doc.get('samples', [])}
    for index, sample in enumerate(doc.get('samples', [])):
        states.append(dict(id=sample['sample_id'], kind='declared_sample_endpoint',
            label=sample.get('sample_label_raw'), material_entity_id=sample.get('refers_to_entity'),
            complete_original_sample=deepcopy(sample), source_pointer=f'/samples/{index}',
            state_description=sample.get('state_description'),
            physical_state_taxonomy_not_automatically_certified=True,
            sample_identity_or_full_binding_not_newly_certified=True))
    for index, step in enumerate(doc.get('process_steps', [])):
        sid = step['step_id']
        operation = dict(id=sid, kind='operation', operation=step.get('process_type'),
            inputs=deepcopy(step.get('input_sample_ids', [])), outputs=deepcopy(step.get('output_sample_ids', [])),
            parameters=[], original_step=deepcopy(step), source_pointer=f'/process_steps/{index}')
        for role, value in (step.get('parameters') or {}).items():
            if value in [None, '', [], {}]:
                continue
            ident = sid + ':parameter:' + str(len(operation['parameters']) + 1)
            param = dict(id=ident, kind='parameter', role=role, value_raw=deepcopy(value),
                operation_id=sid, complete_step_scope_sha256=canonical(step),
                input_sample_ids=operation['inputs'], output_sample_ids=operation['outputs'],
                no_default_unit_or_numeric_conversion=True)
            operation['parameters'].append(param)
            parameters.append(deepcopy(param))
        operations.append(operation)
        bindings.append(dict(id=sid + ':binding', kind='binding', operation_id=sid,
            inputs=operation['inputs'], outputs=operation['outputs'],
            unresolved_input_or_output_ids=[s for s in operation['inputs'] + operation['outputs'] if s not in samples],
            complete_step_and_endpoint_scope_required=True))
    # Preserve explicit native material flow, as the original workflow did.
    # An output-to-input link is distinct from array order or an equal name.
    orders = deepcopy(doc.get('orders') or [])
    flow, unresolved = native_material_flow(doc.get('process_steps', []))
    explicit_pairs = {(e.get('before'), e.get('after')) for e in orders if isinstance(e, dict)}
    orders.extend(e for e in flow if (e['before'], e['after']) not in explicit_pairs)
    return dict(states=states, operations=operations, parameters=parameters,
        bindings=bindings, orders=orders, no_array_order_edges_created=True,
        unresolved_native_material_flows=unresolved,
        no_cross_namespace_sample_identity_merges=True)


def native_material_flow(steps):
    producers = {}
    for i, step in enumerate(steps):
        for sid in set(step.get('output_sample_ids', [])):
            producers.setdefault(sid, set()).add(i)
    candidates = {}
    pending = []
    for i, before in enumerate(steps):
        for j, after in enumerate(steps):
            if i == j:
                continue
            shared = sorted(set(before.get('output_sample_ids', [])) & set(after.get('input_sample_ids', [])))
            if not shared:
                continue
            if any(len(producers[sid]) != 1 for sid in shared):
                pending.append(dict(before_index=i, after_index=j, shared_sample_ids=shared,
                    reason='native_endpoint_has_multiple_producers_scope_unresolved'))
                continue
            candidates[(i, j)] = shared

    def reachable(start, target):
        seen = set()
        queue = [start]
        while queue:
            node = queue.pop()
            if node == target:
                return True
            if node in seen:
                continue
            seen.add(node)
            queue.extend(b for a, b in candidates if a == node and b not in seen)
        return False

    result = []
    for (i, j), shared in candidates.items():
        if reachable(j, i):
            pending.append(dict(before_index=i, after_index=j, shared_sample_ids=shared,
                reason='native_material_flow_cycle_not_asserted_as_time_order'))
            continue
        before, after = steps[i], steps[j]
        result.append(dict(id='native_flow:' + before['step_id'] + '>' + after['step_id'],
            kind='order', before=before['step_id'], after=after['step_id'], shared_sample_ids=shared,
            before_index=i, after_index=j, basis='native_declared_output_to_input_material_flow',
            before_complete_step_sha256=canonical(before), after_complete_step_sha256=canonical(after),
            full_endpoint_identity_state_and_source_support_still_required=True,
            no_array_position_or_equal_polymer_name_used=True,
            transitive_closure_not_added=True))
    return result, pending


def process_document(doc, stage0, *, property_source, stage0_source):
    before = canonical(doc)
    rows, counts = restore_coordinates(doc, stage0)
    tables = {b['block_id']: b for b in stage0.get('elements', []) if b.get('type') == 'table'}
    blocks = {b['block_id']: b for b in stage0.get('elements', [])}
    evidence = {e['evidence_id']: e for e in doc.get('evidence', []) if e.get('evidence_id')}
    for row in rows:
        apply_typed_scopes(row, tables, counts)
        owner = row['owner_path']
        apply_stage_roles(row, resolve(doc, owner), evidence, tables, counts)
        if re.fullmatch(r'/property_series/\d+/points/\d+', owner):
            point = resolve(doc, owner)
            series = resolve(doc, owner.rsplit('/points/', 1)[0])
            unknown = [eid for eid in point.get('evidence_ids', []) if eid not in evidence]
            if unknown:
                row['qualifier_recovery_pending_missing_evidence'] = unknown
                counts['qualifier_owners_missing_evidence'] += 1
            else:
                parameter = qualifiers.interpret(point, series, evidence, blocks)
                if parameter:
                    row['material_direct_parameter_contexts'] = [parameter]
                    row['revision_map'].append(dict(rule='source_qualified_scalar',
                        active_parameter_sha256=canonical(parameter), original_point_retained=True))
                    counts['source_qualified_parameters'] += 1
                    counts['qualifier:' + parameter['active_value_semantics']['relation']] += 1
        # Every old qualifier/clause remains present in the effective context,
        # the explicit replacement, or the immutable original owner's lineage.
        row['all_unmodified_original_clauses_remain_active'] = True
    active, pending, more = recover_descriptions(doc, blocks, evidence)
    counts.update(more)
    graph = native_graph(doc)
    counts.update(native_operations=len(graph['operations']), native_parameters=len(graph['parameters']),
        native_sample_endpoints=len(graph['states']), native_orders=len(graph['orders']))
    assert canonical(doc) == before
    return dict(version=VERSION, execution_mode='immutable_cache_recovery_no_api',
        property_source=property_source, original_stage0_source=stage0_source,
        native_process_context=dict(samples=deepcopy(doc.get('samples', [])),
            process_steps=deepcopy(doc.get('process_steps', []))),
        process_graph=graph, effective_process_contexts=rows,
        recovered_operation_history=active, pending_history_recovery=pending,
        property_values_units_sample_ids_and_bindings_unchanged=True,
        all_five_reference_coverage_and_output_support_not_yet_scored=True,
        no_reference_or_score_inputs=True, no_historical_per_paper_acceptance_inputs=True,
        complete_158_paper_specific_source_graphs_not_inherited=True,
        source_location_alignment_does_not_certify_semantic_support=True,
        counts=dict(counts), external_api_calls=0)
