"""Do not inherit one polymer entity onto its explicitly separate monomer column."""
import copy
import re
from stages.source_table_relations import norm
from stages.table_grid import parse_table_cells

VERSION = '1.0.0'


def label(point, blocks, grids):
    candidates = []
    for coordinate in point.get('coordinates', []):
        if coordinate.get('name_raw') != 'source sample label': continue
        raw = coordinate.get('value_raw', '').strip()
        proof = coordinate.get('evidence') or {}
        table = blocks.get(proof.get('block_id'), {})
        locator = proof.get('table_locator') or {}
        if table.get('type') != 'table' or not raw: continue
        body = table.get('table_body') or table.get('text') or ''
        if '<table' not in body.lower(): continue
        if table['block_id'] not in grids:
            grids[table['block_id']] = {c.cell_id: c.model_dump() for c in parse_table_cells(body, table['block_id'])}
        cell = next((c for c in table.get('table_cells', []) if c['cell_id'] == locator.get('cell_id')), None)
        if not cell or grids[table['block_id']].get(cell['cell_id'], {}).get('text') != cell['text']: continue
        if norm(cell['text']) != norm(raw): continue
        candidates.append((raw, table, proof))
    return candidates[0] if len(candidates) == 1 else None


def repair(stage4, stage0, stage2, stage3):
    result = copy.deepcopy(stage4); changes = []; grids = {}
    blocks = {b['block_id']: b for b in stage0['elements']}
    entities = {e['entity_id']: e for e in stage2['polymer_entities']}
    specimens = stage3.get('samples', [])
    for series in result.get('property_series', []):
        entity_id = series.get('entity_id'); entity = entities.get(entity_id)
        if not entity or series.get('sample_id'): continue
        aliases = {norm(n) for n in [entity.get('polymer_name', ''), *entity.get('source_names', [])] if n}
        labels = [label(p, blocks, grids) for p in series['points']]
        if any(l is None for l in labels): continue
        matching = {raw for raw, _, _ in labels if norm(raw) in aliases}
        other = {raw for raw, _, _ in labels if norm(raw) not in aliases}
        if len(matching) != 1 or len(other) != 1: continue
        polymer, monomer = next(iter(matching)), next(iter(other))
        if not any(norm(s.get('sample_label_raw', '')) == norm(monomer) and not s.get('refers_to_entity') for s in specimens):
            continue
        def defined_pair(table):
            caption = table.get('caption') or ''
            return bool(re.search(r'\b'+re.escape(monomer)+r'\b[\s\S]*?\bits\s+polymer[\s\S]*?\b'+re.escape(polymer)+r'\b',caption,re.I))
        if not all(defined_pair(t) for _, t, _ in labels): continue
        # Only a mistaken inherited assignment is changed. Already explicit
        # point-level entity/sample bindings must be compatible or we abstain.
        if any(norm(raw) not in aliases and (p.get('sample_id') or p.get('entity_id'))
               for p, (raw, _, _) in zip(series['points'], labels)): continue
        series.pop('entity_id', None)
        for point, (raw, table, proof) in zip(series['points'], labels):
            before = {'point_entity_id': point.get('entity_id'), 'parent_entity_id': entity_id}
            if norm(raw) in aliases and not point.get('entity_id'):
                point['entity_id'] = entity_id
            point['sample_label_raw'] = raw
            if proof not in point['evidence']: point['evidence'].append(proof)
            changes.append({'record_id':series['series_id']+':'+point['point_id'], 'before':before,
                            'source_label':raw,'entity_id':point.get('entity_id'),
                            'caption':table['caption'],'source_label_proof':proof,
                            'monomer_canonical_sample_not_invented':norm(raw) not in aliases})
    return result, {'version':VERSION,'changes':changes,'reference_answers_loaded':False,
                    'no_new_entities_or_samples':True,'quantities_units_methods_processes_preserved':True}

