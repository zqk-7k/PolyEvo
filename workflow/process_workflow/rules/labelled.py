"""Frozen pure rules; batch entry points and dataset constants removed."""
import re
from .descriptions import VERBS, TIME, RAMP, NEGATION, MEASUREMENT
from .nominal import OTHER_ACTION

LABEL = re.compile('^\\s*(?:(?:bulk|cationic|anionic|radical|solution|suspension|emulsion)\\s+)?polymeri[sz]ation\\s+(?:with|at|in)\\b', re.I)

TEMP = re.compile('(?<![\\w.])[-+\\u2212]?\\d+(?:\\.\\d+)?\\s*°\\s*[CFK]\\b(?!\\s*/)', re.I)

REAGENT = re.compile('\\bwith\\s+([A-Za-z0-9][A-Za-z0-9/·() -]*?)(?:,\\s*(\\d+(?:\\.\\d+)?\\s*(?:mmoles?|mmol|moles?|mol|mg|g)))?,?\\s+(?:at|in)\\b', re.I)

MEDIUM = re.compile('\\bin\\s+([A-Za-z][A-Za-z0-9()/ -]*?)\\s+for\\s+\\d', re.I)

def propose(text, sample_id):
    if not isinstance(text, str) or not LABEL.search(text):
        return None
    if VERBS.search(text) or OTHER_ACTION.search(text) or NEGATION.search(text) or MEASUREMENT.search(text):
        return None
    params = []

    def add(role, m, index=0):
        a, b = m.span(index)
        if a >= 0:
            params.append({'role': role, 'value_raw': text[a:b], 'description_span': [a, b]})
    ramps = [m.span() for m in RAMP.finditer(text)]
    for m in TEMP.finditer(text):
        if not any((a <= m.start() < b for a, b in ramps)):
            add('temperature', m)
    for m in TIME.finditer(text):
        if not m.start() or not re.match('[A-Za-z0-9_.]', text[m.start() - 1]):
            add('duration', m)
    for m in REAGENT.finditer(text):
        add('reaction_reagent_as_reported', m, 1)
        if m.group(2):
            add('reaction_reagent_amount_as_reported', m, 2)
    for m in MEDIUM.finditer(text):
        add('reaction_medium_as_reported', m, 1)
    params.sort(key=lambda p: p['description_span'])
    assert len({(p['role'], tuple(p['description_span'])) for p in params}) == len(params)
    return {'sample_id': sample_id, 'operation_type': 'polymerization', 'operation_description': text, 'description_span': [0, len(text)], 'parameters': params, 'order_relations': [], 'intermediate_material_states': [], 'input_state_unknown': True, 'source_support_checked': False, 'accepted_into_prediction': False, 'not_an_inference_of_sample_phase': True, 'change_type': 'existing_description_restructuring'}
