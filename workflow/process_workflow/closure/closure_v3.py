"""Isolated direct prior-field source closure; no model or network operations."""
import sys
sys.dont_write_bytecode = True
import argparse
from copy import deepcopy
import json
from pathlib import Path
from . import closure_v2 as old

PROTOCOL = 'source_closure_prior_field_v3'
WORK = Path(__file__).resolve().parent
BINDING_FILES = ('closure_v3.py', 'closure_v2.py', 'native_owner_completion_frozen.py', 'protocol.md')
ROLES = {'unreviewed', 'physical', 'nonphysical', 'metadata', 'mixed', 'outcome'}
require, sha, decode, canonical = old.require, old.sha, old.decode, old.canonical


def engine_binding():
    return {name: sha((WORK / name).read_bytes()) for name in BINDING_FILES}


def base_packet(packet):
    result = {k: deepcopy(v) for k, v in packet.items()
              if k not in {'prior_fields', 'engine_binding'}}
    result['protocol'] = old.PROTOCOL
    return result


def prior_fields(packet):
    bundle = packet['prior_bundle']
    return ([] if bundle is None else [dict(f, prior_file_sha256=packet['prior_file']['sha256'])
        for k, value in bundle['graph'].items() if k not in old.METADATA_ROOTS
        for f in old.leaves(value, '/' + old.token(k))])


def prepare(native_bytes, source_bytes, native_pin, source_pin, prior_bytes=None, prior_pin=None):
    result = old.prepare(native_bytes, source_bytes, native_pin, source_pin, prior_bytes, prior_pin)
    result['protocol'] = PROTOCOL
    result['prior_fields'] = prior_fields(result)
    result['engine_binding'] = engine_binding()
    return result


def blank_role():
    return dict(role='unreviewed', reason='No direct source role decision submitted', source_anchors=[])


def segment_for(value):
    return dict(start=0 if isinstance(value, str) else None,
                end=len(value) if isinstance(value, str) else None,
                disposition='unresolved', reason=None, source_anchors=[], replacement_ids=[],
                entire_segment_superseded=False,
                original_segment_sha256=canonical(value))


def template(packet=None):
    result = old.template(base_packet(packet) if packet is not None else None)
    result['protocol'] = PROTOCOL
    result['packet_sha256'] = canonical(packet) if packet is not None else None
    result['prior_fields'] = [] if packet is None else [dict(pointer=f['pointer'], sha256=f['sha256'],
        prior_file_sha256=f['prior_file_sha256'], role_decision=blank_role(),
        segments=[segment_for(f['value'])]) for f in packet['prior_fields']]
    return result


def check_packet(packet):
    require(packet.get('protocol') == PROTOCOL, 'Wrong v3 packet protocol')
    old.check_packet(base_packet(packet))
    require(packet['prior_fields'] == prior_fields(packet), 'Prior leaf roster or immutable full file binding changed')
    require(packet['engine_binding'] == engine_binding(), 'Code/protocol/template binding changed')
    require(set(packet) == set(base_packet(packet)) | {'prior_fields', 'engine_binding'}, 'Unexpected packet fields')
    return packet['prior_fields']


def old_closure(packet, closure):
    result = {k: deepcopy(v) for k, v in closure.items() if k != 'prior_fields'}
    result['protocol'] = old.PROTOCOL
    result['packet_sha256'] = canonical(base_packet(packet))
    return result


def direct_prior_ledger(packet, closure):
    fields = packet['prior_fields']; decisions = closure['prior_fields']
    require(isinstance(decisions, list) and [d.get('pointer') for d in decisions] == [f['pointer'] for f in fields],
            'Missing/reordered/duplicate direct prior scientific field')
    if not fields:
        return []
    # The v2 segment/evidence/scope validator is reused verbatim on one explicit
    # synthetic validation owner. This object is never a physical assertion.
    payload = {k: deepcopy(v) for k, v in packet['prior_bundle']['graph'].items() if k not in old.METADATA_ROOTS}
    native = {'direct_prior_validation_owner': payload}
    raw = json.dumps(native, ensure_ascii=False).encode('utf-8')
    source_raw = json.dumps(packet['source_document'], ensure_ascii=False).encode('utf-8')
    fake = old.prepare(raw, source_raw, dict(path='in_memory_prior_validation', sha256=sha(raw)),
        dict(path='in_memory_source_validation', sha256=sha(source_raw)))
    base = old.template(fake)
    base.update(completed=True, source_coverage=deepcopy(closure['source_coverage']),
                graph_nodes=deepcopy(closure['graph_nodes']))
    target = base['owners'][0]
    transformed = []
    for field, d in zip(fields, decisions):
        require(set(d) == {'pointer', 'sha256', 'prior_file_sha256', 'role_decision', 'segments'}, 'Exact direct prior contract required')
        require(d['sha256'] == field['sha256'] and d['prior_file_sha256'] == packet['prior_file']['sha256'], 'Wrong full prior/value binding')
        role = d['role_decision']
        require(isinstance(role, dict) and set(role) == {'role', 'reason', 'source_anchors'}, 'Explicit source-owned role contract required')
        require(role['role'] in ROLES and isinstance(role['reason'], str) and role['reason'].strip(), 'Invalid source-owned field role')
        if role['role'] != 'unreviewed' or role['source_anchors']:
            old.anchors(role['source_anchors'], old.source_blocks(packet))
        parts = []
        require(isinstance(d['segments'], list), 'Direct prior segments required')
        for seg in d['segments']:
            require(set(seg) == set(segment_for(field['value'])), 'Exact direct span/hash contract required')
            if isinstance(field['value'], str):
                start, end = seg['start'], seg['end']
                require(type(start) is int and type(end) is int, 'Direct prior string offsets required')
                part = field['value'][start:end]
            else:
                part = field['value']
            require(seg['original_segment_sha256'] == canonical(part), 'Wrong complete original prior span hash')
            parts.append({k: deepcopy(v) for k, v in seg.items() if k != 'original_segment_sha256'})
        transformed.append(dict(pointer='/direct_prior_validation_owner' + field['pointer'], sha256=field['sha256'], segments=parts))
    target['fields'] = transformed
    ledger = old.validate(fake, base)['native_field_ledger']
    by_pointer = {d['pointer']: d for d in decisions}
    for item in ledger:
        path = item.pop('field_pointer').removeprefix('/direct_prior_validation_owner')
        item.pop('owner_pointer'); item.pop('owner_sha256'); item.pop('parent_pointer')
        item.update(prior_pointer=path, prior_file_sha256=packet['prior_file']['sha256'],
                    field_pointer=path, role_decision=deepcopy(by_pointer[path]['role_decision']))
        item['source_disposition']['original_segment_sha256'] = item['original_value_sha256']
    return ledger


def track_signature(item):
    return (item['active'], item['status'], tuple(sorted(item['source_disposition']['replacement_ids'])))


def merge_prior(packet, direct, aliases):
    output = []
    by_pointer = {f['pointer']: f for f in packet['prior_fields']}
    direct_index = {}
    literal_index = {}
    for item in direct:
        direct_index.setdefault(item['prior_pointer'], []).append(item)
    for item in aliases:
        if 'literal_native_origin' in item:
            literal_index.setdefault(item['alias_pointer'], []).append(item)
    for path, field in by_pointer.items():
        ds = direct_index.get(path, [])
        ls = literal_index.get(path, [])
        if not ls:
            for d in ds:
                output.append(dict(d, decision_origin='direct_source' if d['source_disposition']['disposition'] not in old.UNKNOWN else 'unreviewed_direct',
                    literal_native_origin=None, direct_track=deepcopy(d), literal_track=None))
            continue
        value = field['value']
        if isinstance(value, str):
            cuts = sorted({0, len(value)} | {x[k] for x in ds + ls for k in ('start', 'end')})
            intervals = list(zip(cuts, cuts[1:])) if value else [(0, 0)]
        else:
            intervals = [(None, None)]
        for start, end in intervals:
            def covering(parts):
                candidates = [x for x in parts if (start is None or x['start'] <= start and x['end'] >= end)]
                require(len(candidates) == 1, 'Ambiguous prior interval coverage')
                return candidates[0]
            d, literal = covering(ds), covering(ls)
            direct_reviewed = d['source_disposition']['disposition'] not in old.UNKNOWN
            if direct_reviewed:
                require(track_signature(d) == track_signature(literal), 'Direct prior and proved literal native disposition conflict at ' + path)
            chosen = d if direct_reviewed else literal
            part = value[start:end] if isinstance(value, str) else value
            output.append(dict(prior_pointer=path, prior_file_sha256=packet['prior_file']['sha256'],
                field_pointer=path, field_sha256=field['sha256'], start=start, end=end,
                original_value=deepcopy(part), original_value_sha256=canonical(part),
                active=chosen['active'], status=chosen['status'], source_disposition=deepcopy(chosen['source_disposition']),
                role_decision=deepcopy(d['role_decision']), decision_origin='direct_and_literal_agree' if direct_reviewed else 'proved_literal_native',
                literal_native_origin=deepcopy(literal['literal_native_origin']),
                direct_track=deepcopy(d), literal_track=deepcopy(literal)))
    return output


def validate(packet, closure):
    check_packet(packet)
    require(set(closure) == set(template()), 'Unexpected/global closure fields refused')
    require(closure['protocol'] == PROTOCOL and closure['packet_sha256'] == canonical(packet), 'Wrong full v3 closure/packet binding')
    require(all(closure[k] is None for k in ('observed_backend_model', 'tokens', 'cost')), 'Unobserved backend/tokens/cost must remain null')
    native = old.validate(base_packet(packet), old_closure(packet, closure))
    direct = direct_prior_ledger(packet, closure)
    aliases = old.alias_ledger(base_packet(packet), native['native_field_ledger'])
    effective = merge_prior(packet, direct, aliases)
    return dict(passed=True, native_field_ledger=native['native_field_ledger'], prior_direct_ledger=direct,
                prior_activity_ledger=effective, graph_nodes=deepcopy(closure['graph_nodes']),
                scientific_accuracy_certified=False, source_read_complete_is_self_report=True)

