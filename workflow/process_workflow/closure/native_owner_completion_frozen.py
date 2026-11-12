"""Pure, lossless native-owner publication; no scientific interpretation or I/O.

The caller must verify native_source's file SHA256 against the parsed native
document. JSON object hashes use the same canonical form as the frozen core.
Coverage means publication/retention, never scientific support or deduplication.
"""
from copy import deepcopy
import hashlib
import json
import re

VERSION = 'native_owner_runtime_completion_v2'
COLLECTION = 'additional_native_owner_contexts'
AUDIT = 'native_owner_completion_audit'
SCIENTIFIC_ROOTS = frozenset({
    'property_observations', 'unresolved_property_observations',
    'specialized_property_observations', 'property_series',
    'measurement_conditions', 'characterizations', 'polymer_entities',
    'material_mentions', 'samples', 'process_steps', 'orders',
})
# Exact names only: an unknown extension is never discarded by a name heuristic.
METADATA_ROOTS = frozenset({
    'evidence', 'source_evidence', 'source_anchors', 'provenance',
    'warnings', 'validation', 'validation_results', 'cost', 'costs',
    'quality', 'quality_report', 'paper', 'paper_metadata', 'schema',
    'schema_version', 'reference_no', 'version', 'extraction_metadata',
    'source_file', 'source_document', 'source_document_sha256',
})


def canonical(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode('utf-8')).hexdigest()


def token(value):
    return str(value).replace('~', '~0').replace('/', '~1')


def pointer(value, path):
    if path == '':
        return value
    if not isinstance(path, str) or not path.startswith('/'):
        raise ValueError('Invalid native owner pointer')
    for item in path[1:].split('/'):
        item = item.replace('~1', '/').replace('~0', '~')
        value = value[int(item)] if isinstance(value, list) else value[item]
    return value


def witness(doc, path):
    return dict(original_context_path=path,
        original_context_sha256=canonical(pointer(doc, path)))


def _references(doc, owner, owner_path):
    """Resolve only explicitly named IDs by literal equality; no inferred link."""
    fields = {
        'measurement_condition_id': ('measurement_conditions', ('measurement_condition_id', 'condition_id', 'id')),
        'measurement_condition_ids': ('measurement_conditions', ('measurement_condition_id', 'condition_id', 'id')),
        'characterization_id': ('characterizations', ('characterization_id', 'id')),
        'characterization_ids': ('characterizations', ('characterization_id', 'id')),
    }
    found = []
    def visit(value, path):
        if isinstance(value, dict):
            for key, member in value.items():
                here = path + '/' + token(key)
                if key in fields:
                    root, id_fields = fields[key]
                    for ident in member if isinstance(member, list) else [member]:
                        matches = []
                        candidates = doc.get(root, [])
                        if isinstance(candidates, list):
                            for i, candidate in enumerate(candidates):
                                if isinstance(candidate, dict) and any(
                                        k in candidate and type(candidate[k]) is type(ident)
                                        and candidate[k] == ident for k in id_fields):
                                    matches.append(witness(doc, '/' + root + '/' + str(i)))
                        found.append(dict(reference_field_path=here,
                            literal_reference=deepcopy(ident), matching_native_contexts=matches,
                            resolution='literal_id_matches_only' if matches else 'unresolved_literal_reference',
                            scientific_scope_or_identity_not_inferred=True))
                else:
                    visit(member, here)
        elif isinstance(value, list):
            for i, member in enumerate(value):
                visit(member, path + '/' + str(i))
    visit(owner, owner_path)
    return found


def complete_native_owners(prediction, native, *, native_source):
    """Return a copy with exactly two additive root keys; safely repeatable."""
    if not isinstance(native, dict) or not isinstance(prediction, dict):
        raise ValueError('Native document and prediction must be objects')
    if not isinstance(native_source, dict) or not isinstance(native_source.get('path'), str) \
            or not re.fullmatch(r'[0-9a-f]{64}', native_source.get('sha256', '')):
        raise ValueError('Require a native file path/SHA256 witness')
    if prediction.get('property_source') != native_source:
        raise ValueError('Completion source must equal prediction property_source')
    result = deepcopy(prediction)
    previous = {key: result.pop(key) for key in (COLLECTION, AUDIT) if key in result}
    effective = {}
    for i, row in enumerate(result.get('effective_process_contexts', [])):
        path = row['owner_path']
        if canonical(pointer(native, path)) != row['original_owner_sha256']:
            raise ValueError('Existing effective owner does not match native source: ' + path)
        if path in effective:
            raise ValueError('Duplicate existing effective owner: ' + path)
        effective[path] = '/effective_process_contexts/' + str(i)
    rows, coverage, excluded = [], [], []
    retained = result.get('native_process_context', {})

    def publish(path, root_path, *, series_path=None, boundary='known_scientific_root'):
        owner = pointer(native, path)
        record = dict(original_owner_path=path, original_owner_sha256=canonical(owner))
        if path in effective:
            record.update(disposition='already_effective_owner', prediction_path=effective[path],
                original_owner_retained_by_existing_source_lineage=True)
        else:
            root_name = root_path[1:].replace('~1', '/').replace('~0', '~')
            preserved = root_name in retained and retained[root_name] == native[root_name]
            if preserved:
                record.update(disposition='complete_native_process_context_retention',
                    prediction_path='/native_process_context' + path)
            else:
                is_series = root_name == 'property_series' and series_path is None \
                    and isinstance(owner, dict) and isinstance(owner.get('points'), list)
                payload = {k: v for k, v in owner.items() if k != 'points'} if is_series else owner
                row = dict(original_owner_path=path, original_owner_sha256=canonical(owner),
                    native_source=deepcopy(native_source),
                    collection_context=witness(native, root_path), publication_boundary=boundary,
                    explicit_native_context_references=_references(native, payload, path),
                    scientific_source_support='unreviewed',
                    sample_stage_operation_and_support_not_inferred=True,
                    scientific_values_units_and_original_clauses_unmodified=True)
                if is_series:
                    row.update(record_kind='series_parent_nonpoint_context',
                        unmodified_original_owner_fields_except_points=deepcopy(payload),
                        original_nonpoint_field_witnesses=[witness(native, path + '/' + token(k))
                            for k in owner if k != 'points'],
                        original_points_context=witness(native, path + '/points'))
                else:
                    row.update(record_kind='complete_native_owner', unmodified_original_owner=deepcopy(owner))
                if series_path is not None:
                    row['parent_series_context'] = witness(native, series_path)
                record.update(disposition='additional_owner_published',
                    prediction_path='/' + COLLECTION + '/' + str(len(rows)))
                rows.append(row)
        coverage.append(record)

    for root_name, value in native.items():
        root_path = '/' + token(root_name)
        if root_name in METADATA_ROOTS:
            excluded.append(dict(original_path=root_path, original_sha256=canonical(value),
                reason='exact_metadata_root_allowlist_not_a_new_physical_claim',
                allowlist_entry=root_name))
            continue
        boundary = ('known_scientific_root' if root_name in SCIENTIFIC_ROOTS
            else 'unknown_native_extension_requires_scope_review')
        if isinstance(value, list):
            if not value:
                coverage.append(dict(original_owner_path=root_path, original_owner_sha256=canonical(value),
                    disposition='empty_collection_no_member_owner', publication_boundary=boundary))
            for i, owner in enumerate(value):
                path = root_path + '/' + str(i)
                publish(path, root_path, boundary=boundary)
                if root_name == 'property_series' and isinstance(owner, dict) and isinstance(owner.get('points'), list):
                    for j in range(len(owner['points'])):
                        publish(path + '/points/' + str(j), root_path,
                            series_path=path, boundary='series_point_with_parent_context')
        else:
            publish(root_path, root_path, boundary=boundary)
    by_path = {item['original_owner_path']: item for item in coverage}
    for row in rows:
        if row['record_kind'] == 'series_parent_nonpoint_context':
            path = row['original_owner_path']
            row['point_owner_coverage'] = [deepcopy(by_path[path + '/points/' + str(i)])
                for i in range(len(pointer(native, path)['points']))]
            row['all_original_fields_and_points_structurally_accounted_for'] = True
    result[COLLECTION] = rows
    result[AUDIT] = dict(version=VERSION, native_source=deepcopy(native_source),
        native_document_canonical_sha256=canonical(native), owner_coverage=coverage,
        excluded_metadata_roots=excluded, metadata_exclusion_allowlist=sorted(METADATA_ROOTS),
        original_prediction_canonical_sha256=canonical({k: v for k, v in prediction.items()
            if k not in (COLLECTION, AUDIT)}),
        original_prediction_fields_values_and_order_preserved=True,
        parent_and_child_owner_overlap_requires_review=True,
        source_support_scope_identity_and_deduplication_not_certified=True,
        external_api_calls=0)
    if previous and previous != {key: result[key] for key in (COLLECTION, AUDIT)}:
        raise ValueError('Existing native owner completion is incomplete or changed')
    return result
