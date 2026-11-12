"""Mechanical contract for a source-reader's first process graph.

This checks provenance and structure, never judges semantic accuracy or scores.
"""
from .common import canonical

LISTS = ('material_identities', 'states', 'operations', 'parameters', 'orders', 'bindings',
         'nonphysical_annotations', 'unresolved_source_items', 'native_dispositions')
RELATIONS = {'exact', 'approximate', 'range', 'lower_bound_inclusive', 'lower_bound_exclusive',
             'upper_bound_inclusive', 'upper_bound_exclusive', 'unresolved'}


def validate(graph, source, source_sha256, native_proposals, reference_no):
    errors = []
    checks = dict(source_anchor_quotes_checked=0, source_cells_checked=0, native_dispositions_checked=0)

    def require(condition, message):
        if not condition:
            errors.append(message)

    require(graph.get('schema_version') == 'portable_process_semantic_v1', 'wrong schema_version')
    require(graph.get('reference_no') == reference_no, 'wrong paper ID')
    require(graph.get('source_document_sha256') == source_sha256, 'wrong source document hash')
    for name in LISTS:
        require(isinstance(graph.get(name), list), 'missing list: ' + name)
    if errors:
        return dict(passed=False, errors=errors, semantic_accuracy_certified=False)
    forbidden = {'reference_items', 'reference_coverage', 'recall', 'precision', 'expected_hits', 'target_score'}
    require(not forbidden & set(graph), 'evaluation information in a prediction graph')
    blocks = {b['block_id']: b for b in source.get('elements', [])}

    def anchors(holder, pointer, required=True):
        values = holder.get('source_anchors', [])
        require(isinstance(values, list) and (bool(values) or not required), 'missing anchors: ' + pointer)
        if not isinstance(values, list):
            return
        for i, a in enumerate(values):
            block = blocks.get(a.get('block_id'))
            quote = a.get('quote')
            p = pointer + '/source_anchors/' + str(i)
            if block is None or not isinstance(quote, str) or not quote:
                errors.append('invalid source block or quote: ' + p)
                continue
            if a.get('cell_id') is not None:
                cells = [c for c in block.get('table_cells', []) if c['cell_id'] == a['cell_id']]
                require(len(cells) == 1 and quote in str(cells[0].get('text', '')), 'quote not in stated source cell: ' + p)
                checks['source_cells_checked'] += 1
            else:
                texts = [block.get(k) for k in ['text', 'caption', 'html', 'table_html', 'table_body', 'content', 'markdown']]
                require(any(isinstance(t, str) and quote in t for t in texts), 'quote not in source block: ' + p)
            checks['source_anchor_quotes_checked'] += 1

    all_ids = []
    maps = {}
    for kind in ['material_identities', 'states', 'operations', 'parameters', 'orders', 'bindings', 'nonphysical_annotations']:
        rows = graph[kind]
        ids = [r.get('id') for r in rows]
        require(all(isinstance(i, str) and i for i in ids), 'missing IDs: ' + kind)
        require(len(ids) == len(set(i for i in ids if isinstance(i, str))), 'duplicate IDs: ' + kind)
        all_ids.extend(i for i in ids if isinstance(i, str))
        maps[kind] = {r['id']: r for r in rows if isinstance(r.get('id'), str)}
        for i, row in enumerate(rows):
            anchors(row, kind + '/' + str(i))
    require(len(all_ids) == len(set(all_ids)), 'IDs are not globally unique')
    materials = maps['material_identities']
    states, ops, params = maps['states'], maps['operations'], maps['parameters']
    for row in materials.values():
        require(row.get('scope_kind') in {'actual_sample', 'reported_group', 'method_template', 'condition_class', 'unresolved'},
            'unknown identity scope: ' + row['id'])
        require(set(row.get('member_ids') or []) <= set(materials), 'dangling group member: ' + row['id'])
        require(row['id'] not in (row.get('member_ids') or []), 'self-containing material group: ' + row['id'])
        require(row.get('scope_kind') != 'reported_group' or bool(row.get('member_ids')),
            'reported group has no declared members: ' + row['id'])
    for row in states.values():
        require(row.get('material_id') in materials, 'dangling state material: ' + row['id'])
        require(isinstance(row.get('stage'), str) and bool(row['stage']), 'missing state stage: ' + row['id'])
        require(isinstance(row.get('state_description'), str) and bool(row['state_description']), 'empty state: ' + row['id'])
    for row in ops.values():
        require(set(row.get('inputs') or []) <= set(states), 'dangling operation input: ' + row['id'])
        require(set(row.get('outputs') or []) <= set(states), 'dangling operation output: ' + row['id'])
        require(set(row.get('parameter_ids') or []) <= set(params), 'dangling operation parameter: ' + row['id'])
        for pid in row.get('parameter_ids') or []:
            if pid in params:
                require(params[pid].get('operation_id') == row['id'], 'inconsistent parameter ownership: ' + pid)
    for row in params.values():
        require(row.get('operation_id') is None or row['operation_id'] in ops, 'dangling parameter operation: ' + row['id'])
        require(row.get('material_id') is None or row['material_id'] in materials, 'dangling parameter material: ' + row['id'])
        require(row.get('relation') in RELATIONS, 'missing parameter relation: ' + row['id'])
    for row in graph['orders']:
        require(row.get('before') in ops and row.get('after') in ops and row.get('before') != row.get('after'),
            'invalid directed operation pair: ' + str(row.get('id')))
    edges = [(row.get('before'), row.get('after')) for row in graph['orders']]
    def reaches(start, target, seen):
        if start == target:
            return True
        if start in seen:
            return False
        seen.add(start)
        return any(reaches(b, target, seen) for a, b in edges if a == start)
    require(not any(reaches(b, a, set()) for a, b in edges), 'strict temporal order contains a cycle')
    for row in graph['bindings']:
        require(row.get('material_id') in materials, 'dangling binding material: ' + str(row.get('id')))
        for field, target in [('operation_ids', ops), ('parameter_ids', params), ('state_ids', states)]:
            require(set(row.get(field) or []) <= set(target), 'dangling binding ' + field + ': ' + str(row.get('id')))
    expected = {r['source_pointer']: r['original_sha256'] for r in native_proposals['native_disposition_requirements']}
    actual = {}
    for i, decision in enumerate(graph['native_dispositions']):
        pointer = decision.get('source_pointer')
        require(pointer in expected and pointer not in actual, 'unexpected/repeated native disposition: ' + str(pointer))
        require(decision.get('original_sha256') == expected.get(pointer), 'wrong native claim hash: ' + str(pointer))
        kind = decision.get('disposition')
        require(kind in {'retained', 'corrected', 'nonphysical_annotation', 'unsupported', 'unresolved'},
            'unknown native disposition: ' + str(pointer))
        require(bool(decision.get('reason')), 'missing native disposition reason: ' + str(pointer))
        replacements = decision.get('replacement_ids') or []
        require(set(replacements) <= set(all_ids), 'dangling native replacement: ' + str(pointer))
        require(bool(replacements) or kind in {'unsupported', 'unresolved'}, 'lost active native claim: ' + str(pointer))
        anchors(decision, 'native_dispositions/' + str(i), required=kind not in {'unsupported', 'unresolved'})
        actual[pointer] = decision
        checks['native_dispositions_checked'] += 1
    require(set(actual) == set(expected), 'incomplete native claim dispositions')
    coverage = graph.get('source_coverage') or {}
    read_ids = set(coverage.get('read_block_ids') or [])
    unread = set(coverage.get('unread_block_ids') or [])
    require(read_ids <= set(blocks) and unread <= set(blocks) and not read_ids & unread, 'invalid source coverage IDs')
    require(read_ids | unread == set(blocks), 'source coverage missing blocks')
    complete = bool(coverage.get('all_source_blocks_read'))
    require(not complete or read_ids == set(blocks) and not unread, 'false complete-source coverage metadata')
    return dict(passed=not errors, errors=errors, counts=checks,
        source_read_complete_self_report=complete, source_read_is_self_report_not_independent_observation=True,
        semantic_accuracy_certified=False, reference_coverage_computed=False,
        checks_do_not_validate_whole_sample_binding_semantics=True)


def retained_unknown_native_claims(graph, doc):
    result = []
    for decision in graph['native_dispositions']:
        if decision['disposition'] not in {'unsupported', 'unresolved'}:
            continue
        pointer = decision['source_pointer']
        parts = pointer.strip('/').split('/')
        value = doc[parts[0]][int(parts[1])]
        assert canonical(value) == decision['original_sha256']
        result.append(dict(source_pointer=pointer, complete_original_claim=value,
            original_sha256=decision['original_sha256'], status='unconfirmed',
            source_reader_disposition=decision, stays_in_output_support_review=True))
    return result
