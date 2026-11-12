"""Frozen pure rules; batch entry points and dataset constants removed."""
import re

VERBS = re.compile('\\b(?:heated|annealed|dried|washed|rinsed|cooled|quenched|polymerized|polycondensed|cast|mou?lded|mixed|blended|pressed|fractured|coated|precipitated|filtered|extruded|stirred)\\b|混練|混合|成形(?!機|机|法|条件)|架橋|挟み|乾燥|干燥|退火|混炼|浇铸|模压|洗涤|冷却|镀金', re.I)

TEMPERATURE = re.compile('(?<![\\w.])(?:about\\s*|approximately\\s*|約\\s*|约\\s*)?[−-]?\\d+(?:\\.\\d+)?(?:\\s*[–~-]\\s*\\d+(?:\\.\\d+)?)?\\s*(?:°\\s*[CFK]|℃|kelvin\\b)(?!\\s*/)', re.I)

RAMP = re.compile('(?<![\\w.])\\d+(?:\\.\\d+)?\\s*(?:°\\s*[CFK]|℃)\\s*/\\s*(?:min|s|h)(?![A-Za-z])', re.I)

TIME = re.compile('(?<![\\w.])(?:about\\s*|approximately\\s*|約\\s*|约\\s*)?\\d+(?:\\.\\d+)?\\s*(?:hours?\\b|hrs?\\b|h\\b|minutes?\\b|mins?\\b|min\\b|seconds?\\b|s\\b|分間|時間|小时|分钟)|\\b(?:several hours|overnight)\\b', re.I)

PRESSURE = re.compile('(?<![\\w.])\\d+(?:\\.\\d+)?\\s*(?:MPa|kPa|Pa|psi|kg/cm[²2])(?![A-Za-z])', re.I)

SPEED = re.compile('(?<![\\w.])\\d+(?:\\.\\d+)?\\s*rpm(?![A-Za-z])', re.I)

NEGATION = re.compile('\\b(?:not|without|never|except|previously|literature|estimated)\\b|未|不|引用|先の報告', re.I)

MEASUREMENT = re.compile('\\b(?:DSC|TGA|DMA|measur\\w*|calibrat\\w*|analys\\w*|scan\\w*)\\b|測定|测量|表征|校准', re.I)

def proposals(text, sample_id):
    rows = []
    for sentence in re.finditer('[^;。;\\n]+', text):
        value = sentence.group()
        verbs = list(VERBS.finditer(value))
        for i, verb in enumerate(verbs):
            eastern = bool(re.search('[\\u3400-\\u9fff]', verb.group()))
            start = (verbs[i - 1].end() if i else 0) if eastern else verb.start()
            stop = verb.end() if eastern else verbs[i + 1].start() if i + 1 < len(verbs) else len(value)
            span = value[start:stop]
            params = []
            for role, pattern in [('temperature', TEMPERATURE), ('temperature_ramp', RAMP), ('duration', TIME), ('pressure', PRESSURE), ('rotation_speed', SPEED)]:
                for m in pattern.finditer(span):
                    params.append({'role': role, 'value_raw': m.group(), 'description_span': [sentence.start() + start + m.start(), sentence.start() + start + m.end()], 'review_status': 'unreviewed'})
            for role, pattern in [('temperature_text', '\\broom temperature\\b|室温'), ('atmosphere_text', '\\bin vacuo\\b|\\bvacuum\\b|真空')]:
                for m in re.finditer(pattern, span, re.I):
                    params.append({'role': role, 'value_raw': m.group(), 'description_span': [sentence.start() + start + m.start(), sentence.start() + start + m.end()], 'review_status': 'unreviewed'})
            rows.append({'sample_id': sample_id, 'operation_token': verb.group(), 'existing_description_clause': span, 'description_span': [sentence.start() + start, sentence.start() + stop], 'parameters': params, 'has_negation_or_external_provenance': bool(NEGATION.search(value)), 'has_measurement_context': bool(MEASUREMENT.search(value)), 'order_relations': [], 'intermediate_material_states': [], 'input_state_unknown': True, 'source_support_checked': False, 'review_status': 'unreviewed', 'accepted_into_prediction': False, 'change_type': 'restructure_existing_description_only'})
    return rows
