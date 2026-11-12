"""Apply explicitly reviewed cross-table composition links without numerical guesses.

The caller supplies source-only proposals. A shared number is insufficient: both
composition headers, an author's component definition, a printed specimen label
and the polymer family must be grounded. Original values, IDs and processes stay.
"""
from __future__ import annotations

import copy
import re

from stages.source_table_relations import entries, norm, witness
from stages.stage4_direct_table_supplement import evidence, plain, table_cell_scalar

VERSION = '1.0.0'


def axis_symbol(raw):
    # Keep case: feed M1 and incorporated m1 are different physical quantities.
    raw = re.sub(r'\^\{[^}]*\}', '', str(raw))
    return re.sub(r'[^A-Za-z0-9]', '', plain(raw))


def apply_specimen_links(stage3, stage4, stage0, proposals):
    s3, s4 = copy.deepcopy(stage3), copy.deepcopy(stage4)
    blocks = {b['block_id']: b for b in stage0['elements']}
    samples = {s['sample_id']: s for s in s3['samples']}
    records = {rid: row for row, parent, rid in entries(s4)}
    changed, rejected, sample_changes = [], [], []

    def cell(locator):
        table = blocks.get(locator.get('table_id'))
        if not table or table.get('type') != 'table':
            raise ValueError('missing source table')
        matches = [c for c in table.get('table_cells', []) if c['cell_id'] == locator.get('cell_id')]
        if len(matches) != 1:
            raise ValueError('missing or ambiguous source cell')
        return table, matches[0]

    for proposal in proposals:
        uid = proposal.get('record_id')
        try:
            row = records[uid]
            sample = samples[proposal['sample_id']]
            rt, rc = cell(proposal['response_composition_cell'])
            it, ic = cell(proposal['identity_composition_cell'])
            lt, lc = cell(proposal['identity_sample_cell'])
            ht, ih = cell(proposal['identity_axis_header'])
            qt, rh = cell(proposal['response_axis_header'])
            if not (it['block_id'] == lt['block_id'] == ht['block_id'] and rt['block_id'] == qt['block_id']):
                raise ValueError('headers and labels must belong to their own tables')
            if ic['row_index'] != lc['row_index'] or ih['column_index'] != ic['column_index'] or rh['column_index'] != rc['column_index']:
                raise ValueError('source row or column does not agree')
            if ih['row_index'] >= ic['row_index'] or rh['row_index'] >= rc['row_index']:
                raise ValueError('not a preceding composition header')
            symbol = proposal['axis_symbol']
            if axis_symbol(ih['text']) != symbol or axis_symbol(rh['text']) != symbol:
                raise ValueError('composition roles differ, e.g. feed versus polymer')
            amount = table_cell_scalar(rc['text'])
            if amount is None or not 0 < amount < 1 or amount != table_cell_scalar(ic['text']):
                raise ValueError('not the same explicitly reported copolymer fraction')
            same = [c for c in it['table_cells'] if c['column_index'] == ic['column_index']
                    and c['row_index'] > ih['row_index'] and table_cell_scalar(c['text']) == amount]
            if len(same) != 1:
                raise ValueError('composition does not identify a unique printed specimen')
            if plain(lc['text']) != sample.get('sample_label_raw') or sample.get('polymer_type') != 'copolymer':
                raise ValueError('specimen label or existing polymer identity does not agree')
            family = proposal['source_family_raw']
            family_proof = witness(proposal['family_evidence'], blocks)
            definition = witness(proposal['composition_definition_evidence'], blocks)
            components = proposal.get('component_names', [])
            quote = proposal['composition_definition_evidence']['quote']
            if not family_proof or norm(family) not in norm(proposal['family_evidence']['quote']):
                raise ValueError('polymer family is not printed in source evidence')
            if (not definition or len(components) != 2 or 'mole fraction' not in quote.lower()
                    or symbol not in axis_symbol(quote)
                    or any(norm(c) not in norm(quote) or norm(c) not in norm(family) for c in components)):
                raise ValueError('author did not define this component fraction and family')
            response_cells = [c for c in rt['table_cells'] if c['row_index'] == rc['row_index']]
            response_ids = {c['cell_id'] for c in response_cells}
            own_evidence = [e for e in row.get('evidence', []) if e.get('block_id') == rt['block_id']
                            and (e.get('table_locator') or {}).get('cell_id') in response_ids]
            if not own_evidence:
                raise ValueError('property is not from the proposed source row')
            own_values = {table_cell_scalar(c['text']) for c in response_cells if c['cell_id'] in
                          {(e.get('table_locator') or {}).get('cell_id') for e in own_evidence}}
            if table_cell_scalar(row.get('value_raw')) not in own_values:
                raise ValueError('property value no longer agrees with its literal source cell')
            proof = [family_proof, definition]
            for table, c in [(it, ic), (it, lc), (it, ih), (rt, rc), (rt, rh)]:
                proof.append(evidence({'table_id': table['block_id'], 'page': table['page'], 'bbox': table.get('bbox')},
                                      c, row_label=plain(lc['text']), column_label=plain(ih['text'])))
            before = copy.deepcopy(row)
            row['sample_id'] = sample['sample_id']
            row['sample_resolution_status'] = 'resolved'
            for coordinate in row.get('coordinates', []):
                if coordinate.get('name_raw') == 'source sample label':
                    coordinate['value_raw'] = plain(lc['text'])
                    coordinate['evidence'] = proof[3]
            coordinates = row.setdefault('coordinates', [])
            family_coordinate = {'name_raw': 'source polymer family', 'value_raw': family, 'evidence': family_proof}
            if not any(c.get('name_raw') == 'source polymer family' for c in coordinates):
                coordinates.append(family_coordinate)
            for e in proof:
                if e not in row['evidence']:
                    row['evidence'].append(e)
            if sample.get('polymer_name') == plain(lc['text']):
                sample_before = copy.deepcopy(sample)
                sample['polymer_name'] = family
                # Keep the original specimen-row evidence. The family evidence
                # is additionally retained on every affected property point.
                sample_changes.append({'sample_id': sample['sample_id'], 'before': sample_before,
                                       'after': copy.deepcopy(sample), 'additional_family_proof': family_proof})
            if row != before:
                changed.append({'record_id': uid, 'before': before, 'after_sample_id': sample['sample_id'],
                                'proof': proof, 'kind': 'source_defined_cross_table_specimen'})
        except (KeyError, ValueError, TypeError) as exc:
            rejected.append({'record_id': uid, 'reason': str(exc)})
    return s3, s4, {'version': VERSION, 'gold_access': False, 'changes': changed,
                    'sample_changes': sample_changes, 'rejected': rejected, 'records_deleted': 0}
