"""Isolated source-only preparation, validation and active-field publication prototype."""
import sys
sys.dont_write_bytecode = True
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from .native_owner_completion_frozen import canonical, pointer, token, complete_native_owners, METADATA_ROOTS

PROTOCOL = 'complete_native_source_closure_v2'
SCOPE = ('subject', 'composition', 'branch', 'stage', 'operation', 'conditions', 'qualifiers')
FORBIDDEN = {'reference_items', 'reference_coverage', 'scores', 'target_score', 'expected_hits',
             'recall', 'precision', 'old_audit', 'audit_directory', 'reference_answers'}
BAD_PARTS = {'reviews', 'review_quality_checks101', 'coordinator_assessments', 'credentials',
             'secrets', '.env', '.git', '__pycache__'}
UNKNOWN = {'unsupported', 'unresolved'}
RESOLVED = {'retained', 'corrected', 'nonphysical'}

def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def decode(data):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            require(k not in result, 'Duplicate JSON key: ' + k)
            result[k] = v
        return result
    return json.loads(data.decode('utf-8-sig'), object_pairs_hook=unique,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))

def reject_feedback(value):
    if isinstance(value, dict):
        require(not FORBIDDEN.intersection(value), 'Reference/score/old-audit fields refused')
        for v in value.values():
            reject_feedback(v)
    elif isinstance(value, list):
        for v in value:
            reject_feedback(v)

def leaves(value, path):
    if isinstance(value, dict) and value:
        for k, v in value.items():
            yield from leaves(v, path + '/' + token(k))
    elif isinstance(value, list) and value:
        for i, v in enumerate(value):
            yield from leaves(v, path + '/' + str(i))
    else:
        yield dict(pointer=path, sha256=canonical(value), value=deepcopy(value))

def owners(native, pin):
    result = complete_native_owners(dict(property_source=pin), native, native_source=pin)
    out = []
    for row in result['native_owner_completion_audit']['owner_coverage']:
        path = row['original_owner_path']; obj = pointer(native, path)
        parent = path.rsplit('/points/', 1)[0] if '/points/' in path else None
        if path.startswith('/property_series/') and '/points/' not in path and isinstance(obj, dict) and isinstance(obj.get('points'), list):
            fields = [f for k, v in obj.items() if k != 'points' for f in leaves(v, path + '/' + token(k))]
            relation = dict(points_pointer=path + '/points', points_sha256=canonical(obj['points']),
                            point_pointers=[path + '/points/' + str(i) for i in range(len(obj['points']))])
        else:
            fields = list(leaves(obj, path)); relation = None
        out.append(dict(pointer=path, sha256=canonical(obj), complete_original_owner=deepcopy(obj),
                        fields=fields, parent_pointer=parent, points_relation=relation))
    return out, result['native_owner_completion_audit']['excluded_metadata_roots']

def prepare(native_bytes, source_bytes, native_pin, source_pin, prior_bytes=None, prior_pin=None):
    require(sha(native_bytes) == native_pin['sha256'] and sha(source_bytes) == source_pin['sha256'], 'Wrong full input file hash')
    native, source = decode(native_bytes), decode(source_bytes)
    require(isinstance(native, dict) and isinstance(source, dict), 'Native/source must be objects')
    reject_feedback(native); reject_feedback(source)
    prior = None
    if prior_bytes is not None:
        require(prior_pin and sha(prior_bytes) == prior_pin['sha256'], 'Wrong full prior file hash')
        prior = decode(prior_bytes); reject_feedback(prior)
        require(set(prior) == {'graph', 'native_origin_index'} and isinstance(prior['graph'], dict) and isinstance(prior['native_origin_index'], list), 'Prior bundle requires graph and explicit native_origin_index')
    rows, excluded = owners(native, native_pin)
    return dict(protocol=PROTOCOL, native_file=deepcopy(native_pin), source_file=deepcopy(source_pin),
                prior_file=deepcopy(prior_pin), native_document=native, source_document=source,
                prior_bundle=prior, native_owners=rows, excluded_metadata_roots=excluded,
                literal_native_id_references=literal_references(native),
                native_predictions_are_prior_not_gold=True, semantic_accuracy_certified=False)

def literal_references(native):
    # Preserve every literal field without interpreting identity by names or value similarity.
    out = []
    def visit(value, path):
        if isinstance(value, dict):
            for k, v in value.items():
                here = path + '/' + token(k)
                if k.endswith(('_id', '_ids')):
                    out.append(dict(pointer=here, sha256=canonical(v), literal_value=deepcopy(v)))
                visit(v, here)
        elif isinstance(value, list):
            for i, v in enumerate(value): visit(v, path + '/' + str(i))
    for k, v in native.items():
        if k not in METADATA_ROOTS: visit(v, '/' + token(k))
    return out

def template(packet=None):
    return dict(protocol=PROTOCOL, packet_sha256=canonical(packet) if packet is not None else None,
                completed=False, previous_closure_sha256=None,
                source_coverage=dict(read_block_ids=[], unread_block_ids=[], all_source_blocks_read=False),
                graph_nodes=[], owners=[] if packet is None else [dict(pointer=o['pointer'], sha256=o['sha256'],
                    fields=[dict(pointer=f['pointer'], sha256=f['sha256'], segments=[dict(
                        start=0 if isinstance(f['value'], str) else None,
                        end=len(f['value']) if isinstance(f['value'], str) else None,
                        disposition='unresolved', reason=None, source_anchors=[], replacement_ids=[],
                        entire_segment_superseded=False)]) for f in o['fields']]) for o in packet['native_owners']],
                observed_backend_model=None, tokens=None, cost=None)

def check_packet(packet):
    require(packet.get('protocol') == PROTOCOL, 'Wrong packet protocol')
    reject_feedback(packet)
    native = packet['native_document']
    rows, excluded = owners(native, packet['native_file'])
    require(rows == packet['native_owners'] and excluded == packet['excluded_metadata_roots'], 'Owner/field/series packet roster or hash changed')
    require(packet['literal_native_id_references'] == literal_references(native), 'Literal references changed')
    return rows

def source_blocks(packet):
    rows = packet['source_document'].get('elements')
    require(isinstance(rows, list), 'Source requires elements')
    require(all(isinstance(b, dict) and isinstance(b.get('block_id'), str) for b in rows), 'Source block IDs required')
    require(len({b['block_id'] for b in rows}) == len(rows), 'Duplicate source block IDs')
    return {b['block_id']: b for b in rows}

def anchors(values, blocks):
    require(isinstance(values, list) and values, 'Continuous source anchors required')
    for a in values:
        block = blocks.get(a.get('block_id'))
        require(block is not None and a.get('block_sha256') == canonical(block), 'Wrong complete source block hash')
        holder = block
        if a.get('cell_id') is not None:
            matches = [c for c in block.get('table_cells', []) if c.get('cell_id') == a['cell_id']]
            require(len(matches) == 1, 'Cell ID not unique')
            holder = matches[0]; require(a.get('cell_sha256') == canonical(holder), 'Wrong full source cell hash')
        field = a.get('text_field')
        require(field in {'text', 'caption', 'html', 'table_html', 'table_body', 'content', 'markdown'}, 'Explicit source text field required')
        text = holder.get(field); start, end, quote = a.get('start'), a.get('end'), a.get('quote')
        require(isinstance(text, str) and type(start) is int and type(end) is int and 0 <= start < end <= len(text), 'Invalid continuous quote offsets')
        require(isinstance(quote, str) and text[start:end] == quote, 'Quote is not the exact continuous source substring')

def graph_map(nodes, blocks):
    require(isinstance(nodes, list), 'graph_nodes required')
    result = {}
    for n in nodes:
        require(set(n) == {'id', 'kind', 'content', 'scope', 'scope_null_reasons', 'source_anchors', 'links'}, 'Exact node contract required')
        ident = n['id']; require(isinstance(ident, str) and ident and ident not in result, 'Missing/duplicate graph identity')
        require(n['kind'] in {'material', 'state', 'operation', 'parameter', 'order', 'binding', 'nonphysical', 'outcome', 'unresolved'}, 'Unknown graph kind')
        require(isinstance(n['scope'], dict) and set(n['scope']) == set(SCOPE), 'Full seven-dimensional own scope required')
        require(isinstance(n['scope_null_reasons'], dict) and set(n['scope_null_reasons']) == {k for k in SCOPE if n['scope'][k] is None}, 'Explicit scope null reasons required')
        require(all(isinstance(v, str) and v.strip() for v in n['scope_null_reasons'].values()), 'Empty scope null explanation')
        if n['kind'] != 'unresolved': anchors(n['source_anchors'], blocks)
        require(isinstance(n['links'], list), 'Explicit links required')
        result[ident] = n
    edges = []
    for n in nodes:
        for link in n['links']:
            require(set(link) == {'role', 'target_id'} and isinstance(link['role'], str) and link['role'], 'Invalid literal link')
            require(link['target_id'] in result, 'Dangling graph reference')
            edges.append((n['id'], link['target_id']))
    def visit(x, seen, active):
        require(x not in active, 'Cyclic identity/reference graph')
        if x in seen: return
        active.add(x)
        for a, b in edges:
            if a == x: visit(b, seen, active)
        active.remove(x); seen.add(x)
    seen = set()
    for x in result: visit(x, seen, set())
    return result

def validate(packet, closure):
    rows = check_packet(packet); blocks = source_blocks(packet)
    require(set(closure) == set(template()), 'Unexpected/global disposition fields refused')
    require(closure['protocol'] == PROTOCOL and closure['packet_sha256'] == canonical(packet), 'Wrong closure/full packet hash')
    require(closure['completed'] is True, 'Blank/incomplete closure is not complete')
    require(isinstance(closure['owners'], list), 'Owner dispositions required')
    require([o.get('pointer') for o in closure['owners']] == [o['pointer'] for o in rows], 'Missing/reordered/duplicate native owner')
    nodes = graph_map(closure['graph_nodes'], blocks)
    cov = closure['source_coverage']; require(set(cov) == {'read_block_ids', 'unread_block_ids', 'all_source_blocks_read'}, 'Exact source coverage contract')
    read, unread = cov['read_block_ids'], cov['unread_block_ids']
    require(isinstance(read, list) and isinstance(unread, list) and len(read) == len(set(read)) and len(unread) == len(set(unread)), 'Duplicate source coverage IDs')
    require(set(read).isdisjoint(unread) and set(read) | set(unread) == set(blocks), 'Source blocks not fully accounted')
    require(type(cov['all_source_blocks_read']) is bool and (not cov['all_source_blocks_read'] or not unread), 'False source-read-complete declaration')
    ledger = []
    for original, decision in zip(rows, closure['owners']):
        require(set(decision) == {'pointer', 'sha256', 'fields'} and decision['sha256'] == original['sha256'], 'Wrong complete native owner hash')
        require([f.get('pointer') for f in decision['fields']] == [f['pointer'] for f in original['fields']], 'Missing/reordered/duplicate original scientific field')
        for field, d in zip(original['fields'], decision['fields']):
            require(set(d) == {'pointer', 'sha256', 'segments'} and d['sha256'] == field['sha256'], 'Wrong original full field hash')
            value = field['value']; segments = d['segments']; require(isinstance(segments, list) and segments, 'Every field needs explicit disposition')
            cursor = 0
            for seg in segments:
                require(set(seg) == {'start', 'end', 'disposition', 'reason', 'source_anchors', 'replacement_ids', 'entire_segment_superseded'}, 'Exact segment contract; global withdrawal refused')
                start, end = seg['start'], seg['end']
                if isinstance(value, str):
                    require(type(start) is int and type(end) is int and start == cursor and start <= end <= len(value) and (start < end or not value and len(segments) == 1), 'String partitions must be contiguous and exhaustive')
                    cursor = end; part = value[start:end]
                else:
                    require(start is None and end is None and len(segments) == 1, 'Non-string field is one exact partition'); part = value
                kind = seg['disposition']; require(kind in UNKNOWN | RESOLVED, 'Unknown disposition')
                require(isinstance(seg['reason'], str) and seg['reason'].strip(), 'Actual disposition reason required')
                require(type(seg['entire_segment_superseded']) is bool, 'Explicit segment supersession required')
                ids = seg['replacement_ids']; require(isinstance(ids, list) and len(ids) == len(set(ids)) and set(ids) <= set(nodes), 'Missing/dangling replacement IDs')
                if kind in RESOLVED or seg['source_anchors']: anchors(seg['source_anchors'], blocks)
                if kind in {'corrected', 'nonphysical'}:
                    require(ids and seg['entire_segment_superseded'] is True, 'Targeted supersession requires replacement graph and explicit full-segment correction')
                    require(all(nodes[x]['kind'] != 'unresolved' for x in ids), 'Unresolved graph cannot supersede native assertion')
                    if kind == 'nonphysical': require(all(nodes[x]['kind'] in {'nonphysical', 'outcome'} for x in ids), 'Nonphysical replacement must be explicit context/outcome')
                    active = False; status = 'explicitly_superseded'
                else:
                    require(not seg['entire_segment_superseded'], 'Unchanged/unknown field cannot be withdrawn')
                    active = True; status = 'active_unknown' if kind in UNKNOWN else 'active_retained'
                ledger.append(dict(owner_pointer=original['pointer'], owner_sha256=original['sha256'], field_pointer=field['pointer'], field_sha256=field['sha256'],
                    start=start, end=end, original_value=deepcopy(part), original_value_sha256=canonical(part), active=active, status=status,
                    source_disposition=deepcopy(seg), parent_pointer=original['parent_pointer']))
            if isinstance(value, str): require(cursor == len(value), 'Missing physical/unknown string suffix')
    return dict(passed=True, native_field_ledger=ledger, graph_nodes=deepcopy(closure['graph_nodes']),
                semantic_accuracy_certified=False, source_read_complete_is_self_report=cov['all_source_blocks_read'])

def alias_ledger(packet, native_ledger):
    prior = packet['prior_bundle']
    if prior is None: return []
    fields = {f['pointer']: f for k, v in prior['graph'].items() if k not in METADATA_ROOTS for f in leaves(v, '/' + token(k))}
    native = {f['pointer']: f for o in packet['native_owners'] for f in o['fields']}
    index = {}
    for row in prior['native_origin_index']:
        require(set(row) == {'alias_pointer', 'alias_sha256', 'derivation', 'native_field_witnesses'}, 'Exact literal origin contract required')
        path = row['alias_pointer']; require(path in fields and path not in index and row['alias_sha256'] == fields[path]['sha256'], 'Missing/duplicate/wrong complete alias field hash')
        require(row['derivation'] in {'literal_copy', 'declared_derived'}, 'Unknown origin derivation')
        require(isinstance(row['native_field_witnesses'], list) and row['native_field_witnesses'], 'Literal origin witnesses required')
        for witness in row['native_field_witnesses']:
            require(set(witness) == {'field_pointer', 'field_sha256'}, 'Exact native origin witness required')
            target = native.get(witness['field_pointer']); require(target and target['sha256'] == witness['field_sha256'], 'Wrong literal native origin/hash')
            if row['derivation'] == 'literal_copy': require(target['sha256'] == fields[path]['sha256'], 'Literal alias content differs from original native field')
        index[path] = row
    native_parts = {}
    for item in native_ledger:
        native_parts.setdefault(item['field_pointer'], []).append(item)
    out = []
    for path, field in fields.items():
        row = index.get(path)
        if row and row['derivation'] == 'literal_copy' and len(row['native_field_witnesses']) == 1:
            target = row['native_field_witnesses'][0]['field_pointer']
            parts = deepcopy(native_parts.get(target, []))
            for part in parts:
                part.update(alias_pointer=path, alias_sha256=field['sha256'], literal_native_origin=deepcopy(row))
                out.append(part)
        else:
            out.append(dict(alias_pointer=path, alias_sha256=field['sha256'], original_value=deepcopy(field['value']), active=True,
                            status='active_unknown', reason='No independently safe literal propagation; prior assertion retained', origin_index=deepcopy(row)))
    return out
