"""Archived duplicate-handling rules used in the retention example."""
import json
from collections import defaultdict
SCIENCE = ('material', 'property', 'value', 'value_max', 'unit', 'method', 'conditions')
CONDITION_METADATA = frozenset(['condition_id', 'evidence_ids', 'other_condition_evidence_ids', 'confidence'])
RULE = 'same_science_same_table_cells_same_context_blocks_condition_registry_v2'

def stable(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def strip_condition_metadata(value):
    """Retain all scientific values, null/empty states and inline source evidence."""
    if isinstance(value, dict):
        return {k: strip_condition_metadata(v) for k, v in value.items()
                if k not in CONDITION_METADATA}
    if isinstance(value, list):
        return [strip_condition_metadata(v) for v in value]
    return value

def science(row):
    return {k: row.get(k) for k in SCIENCE}

def source_key(row):
    # Identical table cells and contextual source blocks prove common provenance.
    # Different snippets from the same method paragraph are retained as aliases.
    # Text-only records still require identical full evidence objects.
    evidence = [{k: v for k, v in ev.items() if k != 'evidence_id'}
                for ev in row.get('evidence', [])]
    if not evidence:
        return None
    if not all(ev.get('block_id') and (ev.get('source_sentence') or ev.get('table_locator'))
               for ev in evidence):
        return None
    table = [ev for ev in evidence if ev.get('table_locator', {}).get('cell_id')]
    if table:
        contextual = [{k: v for k, v in ev.items() if k != 'source_sentence'}
                      for ev in evidence if not ev.get('table_locator', {}).get('cell_id')]
        return ('table_cells_and_context_blocks',
                tuple(sorted(set(stable(ev) for ev in table))),
                tuple(sorted(set(stable(ev) for ev in contextual))))
    return ('identical_text_evidence', tuple(sorted(set(stable(ev) for ev in evidence))))

def merge_key(row):
    sources = source_key(row)
    if sources is None:
        return None
    payload = science(row)
    payload['conditions'] = strip_condition_metadata(payload['conditions'])
    return stable(payload), sources

def propose(rows):
    """Choose the first frozen native representative, irrespective of any labels."""
    groups = defaultdict(list)
    for row in rows:
        key = merge_key(row['record'])
        if key is not None:
            groups[(row['reference_no'], key)].append(row)
    aliases = {}
    changes = []
    for group in groups.values():
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda r: (r['native_order'], r['source_record_id']))
        keeper = ordered[0]
        for row in ordered[1:]:
            aliases[row['id']] = keeper['id']
            changes.append({
                'rule': RULE, 'reference_no': row['reference_no'],
                'action': 'merge_duplicate_occurrence', 'prediction_id': row['id'],
                'source_record_id': row['source_record_id'],
                'representative_prediction_id': keeper['id'],
                'representative_source_record_id': keeper['source_record_id'],
                'selection': 'earliest_position_in_frozen_native_projection',
                'scientific_fields_changed': [],
                'conditions_before': row['record']['conditions'],
                'conditions_representative': keeper['record']['conditions'],
                'evidence': row['record']['evidence'],
                'source_final_sha256': row['source_final_sha256'],
                'source_final_path': row['source_final_path'],
            })
    return aliases, changes
