"""Frozen pure rules; batch entry points and dataset constants removed."""
import re
from copy import deepcopy
from ..common import canonical

QUALIFIERS = {'up to': 'upper_bound_inclusive', 'at most': 'upper_bound_inclusive', 'within': 'upper_bound_inclusive', 'at least': 'lower_bound_inclusive', 'greater than': 'lower_bound_exclusive', 'above': 'lower_bound_exclusive', 'less than': 'upper_bound_exclusive', 'below': 'upper_bound_exclusive', 'about': 'approximate', 'around': 'approximate', 'approximately': 'approximate', 'SOURCEAPPROX': 'approximate'}

def plain(text):
    s = re.sub('<[^>]+>', '', str(text))
    s = s.replace('\\sim', ' SOURCEAPPROX ').replace('\\circ', '°').replace('\\mu', 'µ')
    s = re.sub('\\\\(?:mathrm|mathbf|mathsf|mathit|text|bf|rm)\\b', '', s)
    s = re.sub('[{}$^~]', '', s).replace('\\ ', ' ')
    s = re.sub('(?<=\\d)\\s+(?=\\d)', '', s)
    return re.sub('\\s+', ' ', s).strip()

def unit_pattern(raw):
    unit = plain(raw).strip().rstrip('.')
    if unit in ['h', 'hr', 'hours', 'hour']:
        return '(?:hours?|hrs?|h)\\b'
    if unit in ['min', 'mins', 'minutes', 'minute']:
        return '(?:minutes?|mins?)\\b'
    if unit in ['day', 'days']:
        return 'days?\\b'
    if unit in ['s', 'sec', 'seconds']:
        return '(?:seconds?|secs?|s)\\b'
    if unit in ['mm', 'µm', 'μm', 'nm']:
        return '\\s*'.join(map(re.escape, unit)) + '\\b'
    if re.fullmatch('°\\s*C', unit):
        return '°\\s*C\\b'
    if unit == 'kGy':
        return 'kGy\\b'
    if unit == 'transferred monolayers' or unit == 'transferredmonolayers':
        return 'transferred\\s+monolayers\\b'
    return None

def interpret(point, series, evidence, blocks):
    coords = point.get('coordinates', [])
    if len(coords) != 1 or coords[0].get('name_raw') != 'source sample label':
        return None
    if any((holder.get(k) for holder in [point, series] for k in ['sample_id', 'sample_ids'])):
        return None
    if ((point.get('measurement_context') or {}).get('other_conditions') or {}).get('fact_role') != 'process_parameter':
        return None
    lo, hi = (point.get('value_min'), point.get('value_max'))
    if not isinstance(lo, (int, float)) or isinstance(lo, bool) or lo != hi:
        return None
    numeric = plain(point.get('value_raw', ''))
    if not re.fullmatch('\\d+(?:\\.\\d+)?', numeric) or float(numeric) != lo:
        return None
    unit = unit_pattern(point.get('unit_raw', ''))
    if not unit:
        return None
    prefixes = '|'.join((re.escape(k) for k in sorted(QUALIFIERS, key=len, reverse=True)))
    pat = re.compile('(?<![\\w.])(?P<qualifier>' + prefixes + ')\\s+(?P<number>' + re.escape(numeric) + ')\\s*' + unit, re.I)
    matches = {}
    for eid in point.get('evidence_ids', []):
        ev = evidence[eid]
        bid = ev.get('block_id')
        b = blocks.get(bid)
        if b is None or b.get('type') not in ['text', 'paragraph']:
            continue
        sentence = plain(ev.get('source_sentence', ''))
        full = plain(b.get('text', ''))
        for m in pat.finditer(sentence):
            if m.group(0).lower() not in full.lower():
                continue
            qualifier = m.group('qualifier')
            key = next((k for k in QUALIFIERS if k.lower() == qualifier.lower()))
            match = dict(evidence_id=eid, block_id=bid, block_sha256=canonical(b), matched_normalized_phrase=m.group(0), qualifier_literal=qualifier, relation=QUALIFIERS[key], original_evidence=deepcopy(ev))
            matches[bid, m.group(0).lower()] = match
    if len(matches) != 1:
        return None
    match = next(iter(matches.values()))
    return dict(interpretation_kind='explicit_source_qualified_scalar_process_parameter', original_extractor_subject_label=deepcopy(coords[0]), original_whole_point_sha256=canonical(point), original_role_literal=series.get('property_name_raw'), primary_parameter=dict(role=series.get('property_name_raw'), value_raw=point['value_raw'], unit_raw=point['unit_raw']), process_subject=dict(scope='literal_source_anchored_parameter_method_or_case', material_label=coords[0]['value_raw'], stage_role_literal=series.get('property_name_raw'), precise_physical_batch_or_canonical_identity_not_inferred=True), active_value_semantics=dict(relation=match['relation'], qualifier_literal=match['qualifier_literal'], matched_source_phrase=match['matched_normalized_phrase'], no_exact_equality_assigned_when_source_is_qualified=True), source_anchors=[dict(block_id=match['block_id'], block_sha256=match['block_sha256'])], source_evidence=deepcopy([evidence[eid] for eid in point.get('evidence_ids', [])]), qualifier_response_evidence_match=match, source_case_is_not_a_unique_physical_batch=True, supersedes_original_exact_min_max_in_process_interpretation_only=True, canonical_property_sample_ids_or_numeric_binding_not_rewritten=True, all_original_other_conditions_remain_mandatory_for_source_review=True, unlisted_original_property_and_process_assertions_remain_active=True)
