"""Bind a multi-row response using both printed specimen code and composition.

An existing sample, its own source identity table and the response table must
agree. Values never identify samples. No reference database is consulted.
"""
import copy
import re
from stages.source_table_relations import norm
from stages.table_grid import parse_table_cells
from stages.stage4_direct_table_supplement import plain

VERSION = '1.0.0'


def repair(stage4, stage0, samples=(), entities=()):
    out = copy.deepcopy(stage4)
    blocks = {b['block_id']: b for b in stage0['elements']}
    specimens = list(samples)
    polymers = {e['entity_id']: e for e in entities}
    grids = {}
    changes = []

    def grid(block):
        bid = block.get('block_id')
        if bid in grids:
            return grids[bid]
        body = block.get('table_body') or block.get('text') or ''
        if block.get('type') != 'table' or '<table' not in body.lower():
            return None
        parsed = {c.cell_id: c.model_dump() for c in parse_table_cells(body, bid)}
        cached = {c['cell_id']: c for c in block.get('table_cells', [])}
        if not cached or any(cid not in parsed or parsed[cid]['text'] != cell['text']
                             for cid, cell in cached.items()):
            return None
        grids[bid] = cached
        return cached

    def identity_row(sample, label, composition, response):
        eid = sample.get('refers_to_entity')
        entity = polymers.get(eid, {})
        aliases = [sample.get('polymer_name', ''), entity.get('polymer_name', ''),
                   *entity.get('source_names', [])]
        if norm(composition) not in {norm(x) for x in aliases if x}:
            return False
        proof = sample.get('evidence') or {}
        identity = blocks.get(proof.get('block_id'), {})
        cells = grid(identity)
        if cells is None:
            return False
        if identity.get('block_id') != response.get('block_id'):
            caption = plain(identity.get('caption') or '')
            number = re.search(r'\btable\s*(\d+)\b', caption, re.I)
            if not number or not re.search(r'\btable\s*'+number[1]+r'\b',
                                           plain(response.get('caption') or ''), re.I):
                return False
        candidates = [c for c in cells.values() if norm(c['text']) == norm(label)
                      and c.get('row_span', 1) == 1]
        matches = []
        for first in candidates:
            headers = [c for c in cells.values() if c['row_index'] < first['row_index']
                       and c['column_index'] == first['column_index']]
            if not any(re.search(r'\b(?:sample|polymer)\s*(?:number|code|no\.?|id)\b',
                                 plain(h['text']), re.I) for h in headers):
                continue
            second = [c for c in cells.values() if c['row_index'] == first['row_index']
                      and c['column_index'] == first['column_index']+1
                      and norm(c['text']) == norm(composition)]
            if len(second) == 1:
                matches.append((first, second[0]))
        return len(matches) == 1

    for series in out.get('property_series', []):
        proposals = []
        for point in series.get('points', []):
            coordinates = []
            for coord in point.get('coordinates', []):
                if coord.get('name_raw') != 'source sample label':
                    continue
                proof = coord.get('evidence') or {}
                block = blocks.get(proof.get('block_id'), {})
                cells = grid(block)
                locator = proof.get('table_locator') or {}
                cell = (cells or {}).get(locator.get('cell_id'))
                if cell and norm(cell['text']) == norm(coord.get('value_raw', '')):
                    coordinates.append((cell, coord, block))
            if len(coordinates) != 2:
                proposals = []
                break
            coordinates.sort(key=lambda x: x[0]['column_index'])
            first, second = coordinates
            if (first[2]['block_id'] != second[2]['block_id']
                    or first[0]['row_index'] != second[0]['row_index']
                    or second[0]['column_index'] != first[0]['column_index']+1):
                proposals = []
                break
            response = first[2]
            cells = grid(response)
            headers = [c for c in cells.values() if c['row_index'] < first[0]['row_index']
                       and c['column_index'] == first[0]['column_index']]
            if not any(re.search(r'\b(?:sample|polymer)\s*(?:number|code|no\.?|id)\b',
                                 plain(h['text']), re.I) for h in headers):
                proposals = []
                break
            responses = []
            for proof in point.get('evidence', []):
                if proof.get('block_id') != response['block_id']:
                    continue
                cell = cells.get((proof.get('table_locator') or {}).get('cell_id'))
                if cell and cell['row_index'] == first[0]['row_index'] and cell['column_index'] > second[0]['column_index']:
                    responses.append(cell)
            if not responses:
                proposals = []
                break
            label, composition = first[0]['text'], second[0]['text']
            matches = [s for s in specimens if norm(s.get('sample_label_raw', '')) == norm(label)
                       and identity_row(s, label, composition, response)]
            if len(matches) != 1:
                proposals = []
                break
            target = matches[0]
            if (point.get('sample_id') not in (None, target['sample_id'])
                    or point.get('entity_id') not in (None, target.get('refers_to_entity'))):
                proposals = []
                break
            proposals.append((point, target, [first[1]['evidence'], second[1]['evidence']]))
        if not proposals or len(proposals) != len(series.get('points', [])):
            continue
        subjects = {(s['sample_id'], s.get('refers_to_entity')) for _, s, _ in proposals}
        for point, target, proofs in proposals:
            before = {k: point.get(k) for k in ('sample_id', 'entity_id', 'sample_resolution_status')}
            after = {'sample_id': target['sample_id'], 'entity_id': target.get('refers_to_entity'),
                     'sample_resolution_status': 'resolved'}
            if before == after:
                continue
            point.update(after)
            changes.append({'record_id': series['series_id']+':'+point['point_id'],
                            'before': before, 'after': after, 'response_row_proofs': proofs,
                            'identity_table_proof': target.get('evidence')})
        if len(subjects) > 1:
            before = {k: series.get(k) for k in ('sample_id', 'entity_id', 'sample_resolution_status')}
            series.update(sample_id=None, entity_id=None, sample_resolution_status='unresolved')
            if before != {k: series.get(k) for k in before}:
                changes.append({'record_id': series['series_id'], 'before': before,
                                'after': {k: series.get(k) for k in before},
                                'reason': 'Distinct source-defined samples bind to individual points, not one inherited entity'})
    return out, {'version': VERSION, 'changes': changes, 'reference_answers_loaded': False,
                 'numeric_values_units_methods_conditions_unchanged': True,
                 'no_samples_or_entities_created': True}
