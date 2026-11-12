"""Frozen pure rules; batch entry points and dataset constants removed."""
import re
from .descriptions import TEMPERATURE, TIME, RAMP, VERBS

REACTION = re.compile('\\bpolymeri[sz]ation\\s+time\\b', re.I)

OTHER_ACTION = re.compile('\\b(?:drying|annealing|quenching|washing|precipitation|extrusion|casting|filtration)\\b', re.I)

SPECIES = '\\[[^\\[\\];\\n]+\\]\\s*(?:0|₀)?'

RATIO = re.compile('(' + SPECIES + '\\s*/\\s*' + SPECIES + ')\\s*=\\s*([−+-]?\\d+(?:\\.\\d+)?)')

CONC = re.compile('(' + SPECIES + ')\\s*=\\s*([−+-]?\\d+(?:\\.\\d+)?\\s*(?:mol\\s*/\\s*L|M)\\b)')

SOLVENT_IN = re.compile('\\bin\\s+([A-Z][A-Za-z0-9()]*)\\b')

SOLVENT_AFTER = re.compile('\\b([A-Z][A-Za-z0-9()]*)\\s+solvent\\b')

SOLVENT_AS = re.compile('(?:^|[;:]\\s*)([A-Za-z][A-Za-z -]+?)\\s+as\\s+solvent\\b', re.I)

def propose(text, sample_id):
    if not isinstance(text, str) or not REACTION.search(text):
        return None
    if VERBS.search(text) or OTHER_ACTION.search(text):
        return None
    params = []

    def add(role, match, group=0, label=None):
        a, b = match.span(group)
        params.append({'role': role, 'value_raw': text[a:b], 'description_span': [a, b], **({'role_label_raw': label} if label is not None else {})})
    ramps = [m.span() for m in RAMP.finditer(text)]
    for role, pattern in [('temperature', TEMPERATURE), ('duration', TIME)]:
        for m in pattern.finditer(text):
            if m.start() and re.match('[A-Za-z0-9_.]', text[m.start() - 1]):
                continue
            if role == 'temperature' and any((a <= m.start() < b for a, b in ramps)):
                continue
            add(role, m)
    for m in CONC.finditer(text):
        add('concentration', m, 2, m.group(1))
    for m in RATIO.finditer(text):
        add('feed_ratio', m, 2, m.group(1))
    for pattern in (SOLVENT_IN, SOLVENT_AFTER, SOLVENT_AS):
        for m in pattern.finditer(text):
            add('solvent', m, 1)
    params = list({(p['role'], tuple(p['description_span'])): p for p in params}.values())
    params.sort(key=lambda p: p['description_span'])
    for p in params:
        a, b = p['description_span']
        assert text[a:b] == p['value_raw']
    return {'sample_id': sample_id, 'operation_type': 'polymerization', 'operation_description': text, 'description_span': [0, len(text)], 'parameters': params, 'order_relations': [], 'intermediate_material_states': [], 'input_state_unknown': True, 'source_support_checked': False, 'accepted_into_prediction': False, 'not_an_inference_of_sample_phase': True, 'change_type': 'existing_description_restructuring'}
