"""Engineering provenance and auditable review records; no scientific scoring."""
import hashlib
import json
import re
import sys
from pathlib import Path

CONTRACT = 'auditable_complete_binding_v2'
SCOPE_FIELDS = ('subjects', 'operations', 'states', 'stage', 'composition', 'conditions', 'qualifiers')
METADATA_SUBTREES = {'source_anchors', 'source_evidence', 'evidence', 'original_evidence'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def reject_optimized():
    require(not sys.flags.optimize, 'Optimized Python is forbidden for evaluation integrity checks')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode('utf-8')).hexdigest()


def roster(rows, label):
    require(isinstance(rows, list) and bool(rows), 'Empty ' + label + ' roster')
    ids = [row['reference_no'] for row in rows]
    require(all(isinstance(i, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', i)
        and not i.endswith('.') and i.split('.')[0].upper() not in
        {'CON', 'PRN', 'AUX', 'NUL', *('COM'+str(n) for n in range(1,10)),
         *('LPT'+str(n) for n in range(1,10))} for i in ids), 'Unsafe ' + label + ' paper ID')
    require(len(ids) == len({i.casefold() for i in ids}), 'Duplicate ' + label + ' paper IDs or Windows path aliases')
    return {row['reference_no']: row for row in rows}


def verify_file(witness, base=None):
    path = Path(witness.get('path', witness.get('snapshot', '')))
    if not path.is_absolute() and base is not None:
        path = Path(base) / path
    require(sha(path) == witness['sha256'], 'Input hash mismatch: ' + str(path))
    return path.resolve()


def verify_freeze(path, required=()):
    path = Path(path).resolve()
    frozen = read(path)
    rows = frozen.get('files')
    require(isinstance(rows, list) and bool(rows), 'Empty frozen file list')
    seen = set()
    for row in rows:
        target = verify_file(row, path.parent)
        key = str(target).casefold()
        require(key not in seen, 'Duplicate frozen file: ' + str(target))
        seen.add(key)
    missing = {str(Path(p).resolve()).casefold() for p in required} - seen
    require(not missing, 'Required files absent from freeze: ' + ', '.join(sorted(missing)))
    return frozen


def verify_prediction_run(run):
    run = Path(run).resolve()
    entries = read(run/'input_manifest.json')['papers']
    ids = roster(entries, 'prediction input')
    summary = read(run/'execution_summary.json')
    require(summary['failed'] == 0 and summary['completed'] == summary['paper_count'] == len(ids),
        'Prediction cohort is incomplete')
    require(set(roster(summary['papers'], 'prediction summary')) == set(ids), 'Summary paper roster differs')
    execution = read(run/'execution_manifest.json')
    require(execution['paper_count'] == len(ids) and execution['paper_ids'] == list(ids),
        'Execution paper roster differs')
    require(execution['input_manifest_sha256'] == sha(run/'input_manifest.json'), 'Execution input manifest changed')
    require(execution['runtime_freeze_sha256'] == sha(run/'runtime_freeze.json'), 'Runtime freeze root changed')
    required = [run/name for name in ('input_manifest.json', 'execution_manifest.json',
        'execution_summary.json', 'runtime_freeze.json', 'process_access_log.json')]
    for ref, entry in ids.items():
        for role in ('native_final', 'stage0'):
            verify_file(entry[role])
        for witness in (entry.get('semantic') or {}).values():
            if isinstance(witness, dict) and 'path' in witness and 'sha256' in witness:
                verify_file(witness)
        folder = run/'papers'/ref
        required.extend(folder/name for name in ('prediction.json', 'status.json', 'structural_validation.json'))
        status = read(folder/'status.json')
        require(status['reference_no'] == ref and status['status'] == 'completed', 'Wrong prediction status identity')
        require(status['prediction_sha256'] == sha(folder/'prediction.json'), 'Prediction status hash mismatch')
        require(status['structural_validation_sha256'] == sha(folder/'structural_validation.json'),
            'Structural validation status hash mismatch')
        prediction = read(folder/'prediction.json')
        require(prediction['reference_no'] == ref, 'Prediction paper identity mismatch')
        if prediction.get('active_primary_process_graph') == 'source_semantic_graph':
            require(prediction.get('source_semantic_lineage_complete') is True
                and prediction.get('first_graph_identity_and_source_checked') is True,
                'Formal evaluation requires complete source-semantic lineage')
            provenance = prediction.get('semantic_stage_input_provenance', {})
            for role in ('graph','first_graph','source_packet','native_proposals','source_inventory','run_log','protocol'):
                require(role in provenance, 'Missing source-semantic provenance: ' + role)
                verify_file(provenance[role])
            require(provenance == entry.get('semantic'), 'Prediction semantic provenance differs from release manifest')
            required.append(folder/'semantic_structural_validation.json')
    verify_freeze(run/'freeze.json', required)
    runtime = read(run/'runtime_freeze.json')
    for row in runtime['files']:
        verify_file(row, run)
    return entries


def pointer(value, path):
    if path == '':
        return value
    require(isinstance(path, str) and path.startswith('/'), 'Invalid exact JSON pointer')
    for token in path[1:].split('/'):
        token = token.replace('~1', '/').replace('~0', '~')
        if isinstance(value, list):
            require(token.isdigit() and str(int(token)) == token, 'Noncanonical array pointer')
            value = value[int(token)]
        else:
            value = value[token]
    return value


def leaves(value, path=''):
    if isinstance(value, dict) and value:
        result = set()
        for key, member in value.items():
            child = path+'/'+str(key).replace('~','~0').replace('/','~1')
            result.update({child} if key in METADATA_SUBTREES else leaves(member, child))
        return result
    if isinstance(value, list) and value:
        return {p for i, member in enumerate(value) for p in leaves(member, path+'/'+str(i))}
    return {path}


def object_witnesses(rows, prediction):
    require(isinstance(rows, list) and bool(rows), 'Missing complete object witnesses')
    result = {}
    for row in rows:
        path = row['prediction_path']
        value = pointer(prediction, path)
        require(isinstance(value, (dict, list)) and bool(value), 'Complete object witness must be a nonempty object or array')
        require(canonical(value) == row['prediction_value_sha256'], 'Complete object witness hash mismatch')
        require(path not in result, 'Duplicate complete object witness')
        result[path] = value
    return result


def check_scope(scope):
    require(isinstance(scope, dict) and set(SCOPE_FIELDS) <= set(scope), 'Incomplete structured scope')
    na = scope.get('not_applicable', {})
    require(isinstance(na, dict), 'Invalid not_applicable scope reasons')
    for field in SCOPE_FIELDS:
        value = scope[field]
        expected = list if field in SCOPE_FIELDS[:3] else str
        require(isinstance(value, expected), 'Invalid scope field: ' + field)
        if isinstance(value, list):
            require(all(isinstance(x, str) and x.strip() for x in value) and len(value) == len(set(value)),
                'Invalid scope identities: ' + field)
        require(bool(value) or isinstance(na.get(field), str) and bool(na[field].strip()),
            'Empty scope field lacks explicit reason: ' + field)


def check_witnesses(rows, prediction, allowed_objects):
    require(isinstance(rows, list) and bool(rows), 'Missing clause/context witnesses')
    for row in rows:
        path = row['prediction_path']
        require(any(path == parent or path.startswith(parent+'/') for parent in allowed_objects),
            'Clause witness lies outside complete objects')
        require(canonical(pointer(prediction, path)) == row['prediction_value_sha256'], 'Clause witness hash mismatch')


def strict_review(task, review, prediction, reference, containers, evidence):
    """Validate records of judgments; equivalence and scientific truth stay human/model judgments."""
    require(review.get('review_contract') == CONTRACT, 'Missing auditable review contract')
    claims = {c['id']: c for c in review['active_raw_output_claims']}
    scopes = {s['id']: s for s in review['container_scope_review']}
    objects = {}
    for claim in claims.values():
        cid = claim['id']
        obj = object_witnesses(claim.get('complete_object_witnesses'), prediction)
        objects[cid] = obj
        for parent in claim['raw_container_ids']:
            path = containers[parent]['prediction_path']
            require(any(path == p or path.startswith(p+'/') for p in obj),
                'Complete object witnesses do not cover the entire declared container')
        check_scope(claim['complete_scope'])
        scope_rows = claim.get('scope_evidence', [])
        require(len(scope_rows) == len(SCOPE_FIELDS) and {r['field'] for r in scope_rows} == set(SCOPE_FIELDS),
            'Missing or duplicate scoped identity/context reviews')
        for row in scope_rows:
            require(row.get('reason'), 'Scope evidence lacks interpretation')
            check_witnesses(row.get('prediction_witnesses'), prediction, obj)
            evidence(row.get('source_evidence', []), required=claim['status']=='supported')
        clauses = claim.get('output_clause_reviews', [])
        expected = {(p, leaf) for p, value in obj.items() for leaf in leaves(value)}
        actual = []
        for row in clauses:
            key = (row['object_path'], row['relative_pointer'])
            require(key in expected, 'Output clause is outside complete object leaves')
            require(row.get('status') in {'supported', 'incorrect', 'unconfirmed', 'context_only',
                'out_of_scope','other_dimension','lineage'}, 'Invalid output clause status')
            require(row.get('reason'), 'Output clause lacks reason')
            absolute=key[0]+key[1]
            if row['status']=='context_only':
                name = key[1].rsplit('/',1)[-1]
                require(name in METADATA_SUBTREES | {'id','schema_version','reference_no','block_id','page',
                    'source_pointer','source_field_path'} or name.endswith('_sha256'),
                    'Scientific output clause cannot be dismissed as context metadata')
            if row['status'] in {'out_of_scope','lineage'}:
                parents=row.get('scope_container_ids',[])
                require(bool(parents) and len(parents)==len(set(parents)) and set(parents)<=set(claim['raw_container_ids']),
                    'Excluded leaf lacks its own container scope mapping')
                field='out_of_scope_clause_paths' if row['status']=='out_of_scope' else 'lineage_clause_paths'
                allowed={'mixed','out_of_scope'} if row['status']=='out_of_scope' else {'mixed','revision_lineage'}
                require(all(scopes[p]['disposition'] in allowed and any(absolute==q or absolute.startswith(q+'/')
                    for q in scopes[p].get(field,[])) for p in parents), 'Excluded leaf not covered by container scope paths')
                evidence(row.get('source_evidence',[]),required=True)
                if row['status']=='out_of_scope':
                    require(row.get('scope_category') in {'property_value','measurement_context','calculated_response',
                        'nonphysical_annotation','program_provenance'}, 'Excluded scientific leaf lacks explicit scope category')
                else:
                    lineage=row.get('lineage_provenance',{})
                    value=pointer(prediction,lineage.get('prediction_path',''))
                    require(isinstance(value,dict) and canonical(value)==lineage.get('prediction_value_sha256')
                        and value.get('disposition') in {'retained','corrected','nonphysical_annotation'},
                        'Lineage leaf lacks an exact confirmed disposition')
                    replacements=lineage.get('replacement_claim_ids',[])
                    require(bool(replacements) and set(replacements)<=set(claims)
                        and all(claims[c]['status']=='supported' for c in replacements),
                        'Lineage cannot hide an unknown or missing replacement claim')
            if row['status']=='other_dimension':
                targets=row.get('other_claim_ids',[])
                require(bool(targets) and len(targets)==len(set(targets)) and set(targets)<=set(claims)
                    and cid not in targets, 'Other-dimension leaf lacks actual other claims')
                for other in targets:
                    target=claims[other]
                    require(target['kind']!=claim['kind'] and set(target['raw_container_ids'])&set(claim['raw_container_ids']),
                        'Other-dimension leaf is not mapped within its container')
                    require(any(r['object_path']+r['relative_pointer']==absolute and r['value_sha256']==row['value_sha256']
                        and r['status'] in {'supported','incorrect','unconfirmed'} for r in target.get('output_clause_reviews',[])),
                        'Other-dimension leaf was dropped or circularly reassigned')
            require(canonical(pointer(obj[key[0]], key[1])) == row['value_sha256'], 'Output clause hash mismatch')
            evidence(row.get('source_evidence', []), required=row['status']=='supported')
            actual.append(key)
        require(len(actual)==len(set(actual)) and set(actual)==expected, 'Incomplete complete-object leaf review')
        if claim['status']=='supported':
            require(all(r['status'] in {'supported','context_only','out_of_scope','other_dimension','lineage'} for r in clauses)
                and any(r['status']=='supported' for r in clauses), 'Supported claim contains unchecked/incorrect clauses')
    references = {r['id']: r for r in reference['fixed_reference_items']}
    for hit in review['coverage_review']:
        if hit['status'] != 'hit':
            continue
        item = references[hit['id']]
        require(hit.get('reference_item_sha256') == canonical(item), 'Reference object hash mismatch')
        target = item.get('complete_reference_item', item)
        expected = leaves(target)
        actual = []
        rows = hit.get('reference_clause_reviews', [])
        for row in rows:
            path = row['reference_pointer']
            require(path in expected and row.get('reason'), 'Invalid reference clause pointer/reason')
            require(row.get('reference_value_sha256') == canonical(pointer(target,path)), 'Reference clause hash mismatch')
            require(row.get('status') in {'matched','metadata'}, 'Hit contains unmatched reference clause')
            if row['status']=='metadata':
                require(path.split('/')[1] in {'id','kind','reference_no','eligibility','source_anchors','source_evidence','evidence'},
                    'Scientific reference clause cannot be dismissed as metadata')
            else:
                ids = row.get('matched_claim_ids', [])
                require(bool(ids) and set(ids) <= set(hit['matched_claim_ids']), 'Clause lacks actual matched claims')
                allowed = {p: value for cid in ids for p,value in objects[cid].items()}
                check_witnesses(row.get('prediction_witnesses'), prediction, allowed)
                evidence(row.get('source_evidence', []), required=True)
            actual.append(path)
        require(len(actual)==len(set(actual)) and set(actual)==expected
            and any(r['status']=='matched' for r in rows), 'Incomplete reference clause correspondence')
        check_scope(hit.get('reference_scope'))
        mapping = hit.get('scope_correspondence', [])
        pairs = []
        for row in mapping:
            cid, field = row['claim_id'], row['field']
            require(cid in hit['matched_claim_ids'] and field in SCOPE_FIELDS, 'Unknown hit scope correspondence')
            left, right = hit['reference_scope'][field], claims[cid]['complete_scope'][field]
            require(row.get('reference_scope_value_sha256')==canonical(left)
                and row.get('claim_scope_value_sha256')==canonical(right), 'Scope correspondence hash mismatch')
            relation = row.get('relation')
            require(relation in {'same','synonym','shared_relation','not_applicable'} and row.get('reason'),
                'Missing explicit scope equivalence basis')
            if relation=='same':
                require(left==right, 'Different scoped identities cannot use same equivalence')
            if relation=='not_applicable':
                require(not left and not right, 'Nonempty identity marked not applicable')
            evidence(row.get('source_evidence', []), required=bool(left or right))
            pairs.append((cid,field))
        expected_pairs = {(cid, field) for cid in hit['matched_claim_ids'] for field in SCOPE_FIELDS}
        require(len(pairs)==len(set(pairs)) and set(pairs)==expected_pairs, 'Incomplete hit scope correspondence')
    for group in review['output_support_groups']:
        basis = group.get('equivalence_basis', {})
        require(basis.get('relation') in {'singleton','same','synonym','shared_relation'} and basis.get('reason'),
            'Missing explicit deduplication equivalence basis')
        ids = group['raw_claim_ids']
        require(basis.get('claim_scope_sha256') == {cid:canonical(claims[cid]['complete_scope']) for cid in ids},
            'Deduplication scope witnesses changed or omitted')
        require(basis.get('claim_object_sha256') == {cid:canonical(claims[cid]['complete_object_witnesses']) for cid in ids},
            'Deduplication object witnesses changed or omitted')
        require(basis['relation']!='singleton' or len(ids)==1, 'Multiple claims cannot use singleton equivalence')
        if len(ids)>1:
            evidence(basis.get('source_evidence', []), required=True)
            require(basis['relation']!='same' or all(claims[cid]['complete_scope']==claims[ids[0]]['complete_scope'] for cid in ids),
                'Different scoped identities cannot be deduplicated as same')
