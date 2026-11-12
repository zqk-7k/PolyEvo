"""Resolve a reversed dispersion heading only from an explicit author definition.

Original table evidence remains intact. No numerical plausibility, benchmark
value, or textbook convention is used to choose the ratio direction.
"""
import copy
import re
from stages.stage4_direct_table_supplement import plain

VERSION = '1.0.1'


def _formula_text(text):
    text = re.sub(r'\\(?:overline|mathrm|mathit|mathsf|text|bar)\b', '', text)
    text = plain(text)
    return re.sub(r'[{}$\s]', '', text)


def repair_defined_dispersion(stage4, stage0):
    out = copy.deepcopy(stage4)
    definitions = []
    reverse_definitions = []
    for block in stage0.get('elements', []):
        if block.get('type') not in {'text', 'footnote'}:
            continue
        raw = block.get('text') or ''
        pattern = _formula_text(raw)
        if re.search(r'polydispersity\(?M_?n/M_?w\)?', pattern, re.I):
            reverse_definitions.append(block['block_id'])
        if not re.search(r'polydispersity\(?M_?w/M_?n\)?', pattern, re.I):
            continue
        definitions.append({'block_id': block['block_id'], 'page': block.get('page', 0),
            'bbox': block.get('bbox'), 'source_type': block['type'],
            'source_sentence': raw, 'table_locator': None})
    if reverse_definitions:
        return stage4, {'changes': [], 'source_definition_ambiguous': True}
    if not definitions:
        return stage4, {'changes': [], 'source_definition_ambiguous': False}
    changes = []
    ordinary = [(r, None, r['property_id']) for r in out.get('properties', [])]
    points = [(p, s, s['series_id'] + ':' + p['point_id'])
              for s in out.get('property_series', []) for p in s.get('points', [])]
    for row, parent, rid in ordinary + points:
        name = row.get('property_name_normalized') or (parent or {}).get('property_name_normalized')
        if name not in {'polydispersity_index', 'polydispersity', 'dispersity'}:
            continue
        context = row.get('measurement_context') or {}
        header = context.get('other_conditions', {}).get('source_response_header', '')
        raw_name = row.get('property_name_raw') or (parent or {}).get('property_name_raw') or ''
        # Both emitted meaning and original linked heading must exhibit the
        # inverted ratio, not an incidental unrelated formula in the paper.
        inverted = lambda text: bool(re.fullmatch(r'M_?n/M_?w', _formula_text(text), re.I))
        clarified = (_formula_text(raw_name).casefold() == 'polydispersity'
                     and 'source_definition_discrepancy' in context.get('other_conditions', {}))
        if not inverted(header) or not (inverted(raw_name) or clarified):
            continue
        before = {'property_name_raw': raw_name, 'source_response_header': header}
        row['property_name_raw'] = 'polydispersity'
        row.setdefault('measurement_context', {'condition_status': 'reported', 'other_conditions': {}})
        mc = row['measurement_context']
        oc = mc.setdefault('other_conditions', {})
        oc['source_response_header'] = 'Polydispersity (Mw/Mn; explicit author method definition)'
        oc['source_definition_discrepancy'] = (
            'The printed table header is Mn/Mw; the author explicitly defines '
            'polydispersity as Mw/Mn in the methods. Original heading remains in table evidence.')
        mc['condition_status'] = 'reported'
        mc.setdefault('other_condition_evidence', {})['source_response_header'] = definitions
        mc['other_condition_evidence']['source_definition_discrepancy'] = definitions
        for proof in definitions:
            if proof not in row.setdefault('evidence', []):
                row['evidence'].append(proof)
        changes.append({'record_id': rid, 'before': before,
            'after': {'property_name_raw': row['property_name_raw'],
                      'source_response_header': oc['source_response_header']},
            'author_definition_evidence': definitions, 'quantities_changed': False,
            'printed_table_evidence_preserved': True})
    return out, {'version': VERSION, 'changes': changes,
                 'reference_answers_loaded': False, 'source_definition_ambiguous': False}
