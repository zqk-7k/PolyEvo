"""Frozen pure rules; batch entry points and dataset constants removed."""
import re, html, unicodedata
from collections import Counter
from ..common import canonical, ROOTS, walk

def norm_value(text):
    return re.sub('\\s+', '', unicodedata.normalize('NFKC', html.unescape(str(text))))

def header_key(text):
    text = unicodedata.normalize('NFKC', html.unescape(str(text))).lower()
    text = re.sub('\\\\(?:mathrm|text|operatorname|mathit)\\s*', '', text)
    return re.sub('[\\s${}_^\\\\]+', '', text)

def looks_like_header(text):
    t = header_key(text)
    return bool(re.search('sample|polymer|copolymer|composition|content|fraction|method|condition|history|solvent|temperature|temp\\.|time|acid|ion|monomer|amine|diol|diamine|molar|concentration|pressure|load|ratio|atmosphere|reagent|hkl|layerline|sidechain|probe|run|code|wt[a-z]|weight|tc[([]|^tc$|^tg[([]|^tg$|^r$|^mr|^n$|^w[12]$|^m$', t))

def covers(cell, row, col):
    return cell['row_index'] <= row < cell['row_index'] + int(cell.get('row_span', 1)) and cell['column_index'] <= col < cell['column_index'] + int(cell.get('column_span', 1))

def source_cell(table, locator, raw):
    cells = table.get('table_cells', [])
    cell_id = locator.get('cell_id')
    exact = [c for c in cells if c.get('cell_id') == cell_id]
    if len(exact) == 1 and norm_value(exact[0].get('text', '')) == norm_value(raw):
        return exact[0]
    r, c = (locator.get('row_index'), locator.get('column_index'))
    if not isinstance(r, int) or not isinstance(c, int):
        return None
    hits = [x for x in cells if covers(x, r, c) and norm_value(x.get('text', '')) == norm_value(raw)]
    return hits[0] if len(hits) == 1 else None

def headers_for(table, cell, requested_col):
    cells = table.get('table_cells', [])
    col = requested_col
    first = [c for c in cells if c['row_index'] == 0 and covers(c, 0, col) and looks_like_header(c.get('text', ''))]
    if len(first) != 1 or cell['row_index'] <= 0:
        return []
    found = [first[0]]
    for r in sorted({c['row_index'] for c in cells if 0 < c['row_index'] < min(cell['row_index'], 3)}):
        hits = [c for c in cells if c['row_index'] == r and covers(c, r, col)]
        if len(hits) != 1:
            break
        x = hits[0]
        text = header_key(x.get('text', ''))
        unit_only = bool(re.fullmatch('[([]?(?:°c|°f|k|%|mol%|wt%|g/mol|gcm[-−]?3|mpa|min|h|hr|s)[)\\]]?', text))
        if x.get('is_header') or unit_only:
            found.append(x)
        else:
            break
    unique = {x['cell_id']: x for x in found}
    return [dict(cell_id=x['cell_id'], text=x.get('text', ''), row_index=x['row_index'], column_index=x['column_index'], row_span=x.get('row_span', 1), column_span=x.get('column_span', 1)) for x in unique.values()]

def propose(doc, stage0):
    tables = {x['block_id']: x for x in stage0['elements'] if x.get('type') == 'table'}
    evidence = {e['evidence_id']: e for e in doc.get('evidence', []) if e.get('evidence_id')}
    result = []
    counts = Counter()
    for root in ROOTS:
        for coord_path, coords, owner_path, owner in walk(doc.get(root, []), '/' + root):
            resolved = []
            unresolved = []
            for i, c in enumerate(coords):
                matches = []
                for eid in c.get('evidence_ids', []):
                    e = evidence.get(eid, {})
                    loc = e.get('table_locator') or {}
                    table = tables.get(loc.get('table_id'))
                    if not table:
                        continue
                    cell = source_cell(table, loc, c.get('value_raw'))
                    col = loc.get('column_index')
                    if not cell or not isinstance(col, int):
                        continue
                    hdr = headers_for(table, cell, col)
                    if not hdr:
                        continue
                    matches.append(dict(table_id=table['block_id'], page=table.get('page'), source_table_sha256=canonical(table), source_caption=table.get('caption'), requested_cell_id=loc.get('cell_id'), source_origin_cell_id=cell['cell_id'], source_cell_sha256=canonical(cell), source_cell_text=cell.get('text', ''), original_header_cells=hdr, source_evidence_id=eid, original_coordinate_index=i, original_name_raw=c.get('name_raw'), value_raw=c.get('value_raw'), unit_raw=c.get('unit_raw')))
                by = {(x['table_id'], x['source_origin_cell_id'], canonical(x['original_header_cells'])): x for x in matches}
                if len(by) != 1:
                    unresolved.append(dict(original_coordinate_index=i, coordinate_sha256=canonical(c), reason='no_unique_matching_original_table_cell_with_recoverable_header', candidate_locations=len(by)))
                    continue
                resolved.append(next(iter(by.values())))
            by = {}
            for c in resolved:
                key = (c['table_id'], c['source_origin_cell_id'], canonical(c['original_header_cells']), norm_value(c['value_raw']))
                if key not in by:
                    by[key] = dict(name_raw=' / '.join((h['text'] for h in c['original_header_cells'])), value_raw=c['value_raw'], original_header_cells=c['original_header_cells'], table_id=c['table_id'], page=c['page'], source_table_sha256=c['source_table_sha256'], source_caption=c['source_caption'], source_origin_cell_id=c['source_origin_cell_id'], source_cell_sha256=c['source_cell_sha256'], source_cell_text=c['source_cell_text'], original_coordinate_aliases=[])
                by[key]['original_coordinate_aliases'].append({k: c[k] for k in ['original_coordinate_index', 'original_name_raw', 'requested_cell_id', 'source_evidence_id', 'unit_raw']})
            if not resolved:
                counts['owners_without_restorable_headers'] += 1
                continue
            items = list(by.values())
            counts['owners_with_restored_headers'] += 1
            counts['coordinate_occurrences_restored'] += len(resolved)
            counts['physical_coordinate_cells_in_overlays'] += len(items)
            counts['same_owner_same_cell_aliases'] += len(resolved) - len(items)
            counts['fully_resolved_owner_arrays'] += not unresolved
            result.append(dict(owner_path=owner_path, owner_sha256=canonical(owner), coordinates_path=coord_path, original_coordinates_sha256=canonical(coords), existing_sample_id=owner.get('sample_id'), existing_entity_id=owner.get('entity_id'), source_header_restored_coordinates=items, unresolved_coordinate_clauses=unresolved, all_coordinate_clauses_structurally_resolved=not unresolved, process_roles_and_full_sample_state_association_semantically_certified=False, semantic_equivalence_across_different_owners_not_inferred=True))
    return (result, dict(counts))
