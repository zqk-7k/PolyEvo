"""General rules plus source-model field decisions; no provider or benchmark code."""
from collections import Counter
from copy import deepcopy
import concurrent.futures
import hashlib
import json
from pathlib import Path

from . import core
from .closure import closure_v3 as engine

VERSION = 'general158-v1'
CHECKLIST = tuple('G%02d' % n for n in range(1, 13))
require, canonical, decode = engine.require, engine.canonical, engine.decode


def digest(path):
    return engine.sha(Path(path).read_bytes())


def pin(path):
    return dict(path=str(Path(path).resolve()), sha256=digest(path))


def load_pin(witness):
    require(isinstance(witness, dict) and set(witness) == {'path', 'sha256'}, 'Exact file pin required')
    raw = Path(witness['path']).read_bytes()
    require(engine.sha(raw) == witness['sha256'], 'Input hash changed: ' + witness['path'])
    return raw


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    return pin(path)


def delta_template(packet):
    return dict(schema='general158_delta_v1', packet_sha256=canonical(packet), completed=False,
        previous_response_sha256=None, source_coverage=dict(read_block_ids=[],
        unread_block_ids=list(engine.old.source_blocks(packet)), all_source_blocks_read=False),
        graph_nodes=[], native_decisions=[], prior_decisions=[], targeted_source_requests=[],
        checklist={key: dict(status='unresolved', reason='Not yet read') for key in CHECKLIST})


def rule_binding():
    root = Path(__file__).parent
    files = [p for p in root.rglob('*.py') if '__pycache__' not in p.parts and not p.name.startswith('test_')]
    files.append(root / 'closure/protocol.md')
    return {p.relative_to(root).as_posix(): digest(p) for p in sorted(files)}


def expand_delta(packet, delta):
    """Sparse transport, exhaustive unknown defaults; no implied approvals."""
    require(isinstance(delta, dict) and set(delta) == set(delta_template(packet)), 'Exact delta contract required')
    require(delta['schema'] == 'general158_delta_v1' and delta['packet_sha256'] == canonical(packet), 'Wrong delta/packet binding')
    require(delta['completed'] is True, 'Incomplete model response')
    require(set(delta['checklist']) == set(CHECKLIST), 'All general rule families must be accounted')
    for key, decision in delta['checklist'].items():
        require(set(decision) == {'status', 'reason'} and decision['status'] in {'reviewed', 'not_applicable', 'unresolved'}
            and isinstance(decision['reason'], str) and decision['reason'].strip(), 'Invalid checklist item: ' + key)
    require(isinstance(delta['targeted_source_requests'], list), 'Source requests must be explicit')
    closure = engine.template(packet)
    closure.update(completed=True, source_coverage=deepcopy(delta['source_coverage']), graph_nodes=deepcopy(delta['graph_nodes']))
    owners = {o['pointer']: o for o in closure['owners']}
    for owner in owners.values():
        for field in owner['fields']:
            field['segments'][0]['reason'] = 'Not reviewed in this response; original assertion remains active and unknown'
    seen = set()
    require(isinstance(delta['native_decisions'], list), 'native_decisions must be a list')
    for submitted in delta['native_decisions']:
        path = submitted.get('pointer')
        require(path in owners and path not in seen, 'Missing/duplicate native decision owner')
        seen.add(path); target = owners[path]
        require(set(submitted) == {'pointer', 'sha256', 'fields'} and submitted['sha256'] == target['sha256'], 'Native owner hash mismatch')
        fields = {f['pointer']: f for f in target['fields']}; used = set()
        for field in submitted['fields']:
            name = field.get('pointer')
            require(name in fields and name not in used, 'Missing/duplicate native decision field')
            used.add(name); fields[name].clear(); fields[name].update(deepcopy(field))
    prior = {f['pointer']: f for f in closure['prior_fields']}
    for field in prior.values():
        field['segments'][0]['reason'] = 'Not reviewed in this response; prior assertion remains active and unknown'
    used = set()
    require(isinstance(delta['prior_decisions'], list), 'prior_decisions must be a list')
    for field in delta['prior_decisions']:
        name = field.get('pointer')
        require(name in prior and name not in used, 'Missing/duplicate prior decision field')
        used.add(name); prior[name].clear(); prior[name].update(deepcopy(field))
    return closure


def typed_nodes(nodes):
    by_id = {n['id']: n for n in nodes}
    temporal = {}
    for node in nodes:
        content = node['content']; require(isinstance(content, dict), 'Node content must be an object')
        kind = node['kind']
        if kind == 'operation':
            require(isinstance(content.get('operation_raw'), str) and content['operation_raw'].strip(), 'Operation literal required')
        if kind == 'parameter':
            require({'name_raw', 'value_raw', 'unit_raw', 'parameter_role', 'relation'} <= set(content), 'Typed parameter fields required')
            require(content['parameter_role'] in {'preparation', 'processing', 'testing'}, 'Yield/recovery/response is not an applied condition')
            require(content['relation'] in {'exact', 'approximate', 'lower_bound', 'upper_bound', 'range', 'unspecified'}, 'Explicit scalar qualifier required')
            if content['relation'] in {'approximate', 'lower_bound', 'upper_bound'}:
                require(isinstance(content.get('qualifier_raw'), str) and content['qualifier_raw'].strip(), 'Literal scalar qualifier required')
            if content['relation'] in {'lower_bound', 'upper_bound'}:
                require(type(content.get('bound_inclusive')) is bool, 'Bound must preserve inclusive/exclusive meaning')
            require(any(l['role'] == 'operation' and by_id[l['target_id']]['kind'] == 'operation' for l in node['links']), 'Parameter must refer to its operation')
        if kind == 'binding':
            for role, kinds in [('subject', {'material'}), ('state', {'state'}), ('operation', {'operation'})]:
                require(any(l['role'] == role and by_id[l['target_id']]['kind'] in kinds for l in node['links']), 'Complete binding endpoint required: ' + role)
        if kind == 'order':
            ends = {}
            for role in ('before', 'after'):
                ids = [l['target_id'] for l in node['links'] if l['role'] == role]
                require(len(ids) == 1 and by_id[ids[0]]['kind'] == 'operation', 'Order requires two literal operation endpoints')
                ends[role] = ids[0]
            temporal.setdefault(ends['before'], []).append(ends['after'])
    visited, active = set(), set()
    def visit(ident):
        require(ident not in active, 'Cyclic operation chronology')
        if ident in visited: return
        active.add(ident)
        for child in temporal.get(ident, []): visit(child)
        active.remove(ident); visited.add(ident)
    for ident in temporal: visit(ident)


def compile_prediction(packet, delta):
    closure = expand_delta(packet, delta)
    checked = engine.validate(packet, closure)
    property_roots = {'property_observations', 'unresolved_property_observations',
        'specialized_property_observations', 'property_series'}
    process_context_fields = {'coordinates', 'measurement_context', 'other_conditions',
        'process_context', 'preparation_context'}
    binding_fields = {'sample_id', 'sample_ids', 'measurement_condition_id', 'measurement_condition_ids',
        'characterization_id', 'characterization_ids', 'polymer_entity_id', 'polymer_entity_ids'}
    for row in checked['native_field_ledger']:
        parts = row['field_pointer'].split('/')[1:]
        if parts and parts[0] in property_roots:
            protected = not process_context_fields.intersection(parts) or bool(binding_fields.intersection(parts))
            require(not protected or row['active'], 'Original property data and bindings are protected; add process context separately')
    require(closure['source_coverage']['all_source_blocks_read'] is True, 'Full source reading is required before publication')
    typed_nodes(checked['graph_nodes'])
    # Full original documents remain in the immutable packet; only decisions are
    # stored again. Unreviewed fields are not multiplied into repeated contexts.
    overrides = []
    counts = Counter()
    for origin, rows in [('native', checked['native_field_ledger']), ('prior', checked['prior_activity_ledger'])]:
        for row in rows:
            counts[origin + ':' + row['status']] += 1
            if row['source_disposition']['disposition'] not in engine.old.UNKNOWN or row['source_disposition']['source_anchors']:
                overrides.append(dict(origin=origin, **{k: deepcopy(row[k]) for k in
                    ('field_pointer', 'field_sha256', 'start', 'end', 'active', 'status', 'source_disposition')}))
    return dict(version=VERSION, packet_sha256=canonical(packet),
        immutable_native_file=packet['native_file'], immutable_source_file=packet['source_file'],
        immutable_prior_file=packet['prior_file'], active_graph_nodes=checked['graph_nodes'],
        field_activity_overrides=overrides, default_field_activity='active_unknown',
        unmodified_and_unknown_fields_remain_active=True, whole_prior_graph_deactivation=False,
        property_values_units_sample_ids_and_bindings_unchanged=True,
        property_evaluation_input='immutable_native_file',
        source_coverage=deepcopy(closure['source_coverage']), checklist=deepcopy(delta['checklist']),
        targeted_source_requests=deepcopy(delta['targeted_source_requests']),
        counts=dict(counts, **{'graph:' + k: v for k, v in Counter(n['kind'] for n in checked['graph_nodes']).items()}),
        scientific_accuracy_certified=False, source_read_complete_is_self_report=True,
        five_dimension_metrics=None, observed_backend_model=None, tokens=None, cost=None,
        local_publication_api_calls=0)


def effective_fields(packet, prediction):
    """Public lossless reader of the compact activity overlay, including unknowns."""
    require(prediction['packet_sha256'] == canonical(packet), 'Wrong activity packet')
    index = {}
    for row in prediction['field_activity_overrides']:
        index.setdefault((row['origin'], row['field_pointer']), []).append(row)
    for origin, fields in [('native', [f for o in packet['native_owners'] for f in o['fields']]), ('prior', packet['prior_fields'])]:
        for field in fields:
            value = field['value']; rows = index.get((origin, field['pointer']))
            if not rows:
                yield dict(origin=origin, field_pointer=field['pointer'], original_value=deepcopy(value), active=True, status='active_unknown')
                continue
            # Overrides may cover only some string spans. Unknown gaps stay active.
            cursor = 0
            for row in sorted(rows, key=lambda r: r['start'] if r['start'] is not None else 0):
                if isinstance(value, str) and cursor < row['start']:
                    yield dict(origin=origin, field_pointer=field['pointer'], original_value=value[cursor:row['start']], active=True, status='active_unknown')
                part = value[row['start']:row['end']] if isinstance(value, str) else value
                yield dict(row, original_value=deepcopy(part))
                cursor = row['end']
            if isinstance(value, str) and cursor < len(value):
                yield dict(origin=origin, field_pointer=field['pointer'], original_value=value[cursor:], active=True, status='active_unknown')


def prepare_one(entry, folder):
    nb, sb = load_pin(entry['native_final']), load_pin(entry['stage0'])
    native, source = decode(nb), decode(sb)
    engine.old.reject_feedback(native); engine.old.reject_feedback(source)
    np = write_bytes(folder / 'native.json', nb); sp = write_bytes(folder / 'source.json', sb)
    if entry.get('prior'):
        prior_raw = load_pin(entry['prior'])
    else:
        recovered = core.process_document(native, source, property_source=np, stage0_source=sp)
        graph = {key: recovered[key] for key in ('process_graph', 'effective_process_contexts',
            'recovered_operation_history', 'pending_history_recovery')}
        prior_raw = json.dumps(dict(graph=graph, native_origin_index=[]), ensure_ascii=False, allow_nan=False).encode('utf-8')
    pp = write_bytes(folder / 'prior.json', prior_raw)
    packet = engine.prepare(nb, sb, np, sp, prior_raw, pp)
    engine.check_packet(packet); engine.old.source_blocks(packet)
    packet_pin = write(folder / 'packet.json', packet)
    full = write(folder / 'closure_template.json', engine.template(packet))
    delta = write(folder / 'delta_template.json', delta_template(packet))
    task = dict(version=VERSION, reference_no=entry['reference_no'], packet=packet_pin,
        full_field_template=full, response_template=delta,
        protocol=pin(Path(__file__).parent / 'closure/protocol.md'),
        output_files=['attempt_001.json', 'attempts.json', 'run_log.json'],
        model_execution_required=True, independent_context_required=True,
        reference_or_score_inputs_allowed=False, scientific_results_not_yet_generated=True)
    return dict(reference_no=entry['reference_no'], packet=packet_pin,
        task=write(folder / 'task.json', task), original_inputs=entry)


def write_bytes(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream: stream.write(raw)
    return pin(path)


def verify_packet(task):
    packet = decode(load_pin(task['packet']))
    pb = load_pin(packet['prior_file']) if packet['prior_file'] else None
    rebuilt = engine.prepare(load_pin(packet['native_file']), load_pin(packet['source_file']),
        packet['native_file'], packet['source_file'], pb, packet['prior_file'])
    require(packet == rebuilt, 'Packet differs from full immutable inputs/runtime/protocol')
    return packet


def publish_one(task, response, folder):
    packet = verify_packet(task)
    client_log_raw = load_pin(response['run_log'])
    client_log = decode(client_log_raw)
    require(isinstance(client_log, dict) and client_log.get('reference_no') == task['reference_no'], 'Client run log identity missing/mismatched')
    receipts, previous, result = [], None, None
    for number, witness in enumerate(response['attempts'], 1):
        raw = load_pin(witness)
        write_bytes(folder / ('attempt_%03d.json' % number), raw)
        try:
            delta = decode(raw)
            require(delta.get('previous_response_sha256') == previous, 'Broken actual first/revision chain')
            result = compile_prediction(packet, delta)
            receipt = dict(attempt=number, sha256=engine.sha(raw), passed=True)
        except Exception as exc:
            result = None
            receipt = dict(attempt=number, sha256=engine.sha(raw), passed=False, error=str(exc))
        receipts.append(receipt); previous = engine.sha(raw)
    write(folder / 'attempt_receipts.json', receipts)
    require(result is not None, 'Final response invalid; all submitted attempts preserved')
    result['prepared_packet'] = task['packet']
    result['response_sha256'] = previous
    result['client_run_log'] = response['run_log']
    write_bytes(folder / 'client_run_log.json', client_log_raw)
    prediction = write(folder / 'prediction.json', result)
    return dict(reference_no=task['reference_no'], prediction=prediction, counts=result['counts'])


def run(args, manifest, runtime):
    """Called only by the unified runner, after its frozen-runtime loader/guards."""
    output = args.output.resolve()
    if args.stage == 'prepare':
        def work(entry): return prepare_one(entry, output / 'papers' / entry['reference_no'])
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            tasks = list(pool.map(work, manifest['papers']))
        return dict(version=VERSION, stage='prepare', papers=tasks, protocol=pin(Path(__file__).parent / 'closure/protocol.md'),
            workflow_binding=rule_binding(),
            model_execution_required=True, semantic_model_executed=False, scientific_metrics=None)
    tasks = decode(load_pin(manifest['prepared_tasks']))
    require(tasks['version'] == VERSION and tasks['stage'] == 'prepare', 'Wrong prepared task batch')
    require(tasks['workflow_binding'] == rule_binding(), 'General workflow code changed since task preparation')
    require(load_pin(tasks['protocol']) == (Path(__file__).parent / 'closure/protocol.md').read_bytes(), 'Source protocol changed')
    task_index = {t['reference_no']: t for t in tasks['papers']}
    require(list(task_index) == [p['reference_no'] for p in manifest['papers']], 'Whole prepared cohort/order must be preserved')
    results, failures = [], []
    for entry in manifest['papers']:
        ref = entry['reference_no']; task = task_index[ref]
        require(task['original_inputs'] == {k: v for k, v in entry.items() if k != 'response'}, 'Publication inputs differ from preparation')
        folder = output / 'papers' / ref
        try:
            result = publish_one(task, entry['response'], folder)
            results.append(result)
        except Exception as exc:
            failures.append(dict(reference_no=ref, error=str(exc)))
    return dict(version=VERSION, stage='publish', completed=len(results), failed=len(failures),
        papers=results, failures=failures, all_submitted_papers_required=True,
        semantic_model_executed_by_this_python_entry=False, scientific_metrics=None,
        complete_candidate158_scientific_reproduction_certified=False)
