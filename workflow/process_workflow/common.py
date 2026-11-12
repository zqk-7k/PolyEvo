import hashlib
import json
from pathlib import Path

ROOTS = ('property_observations', 'unresolved_property_observations',
         'specialized_property_observations', 'property_series')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def resolve(value, path):
    for part in path.strip('/').split('/'):
        part = part.replace('~1', '/').replace('~0', '~')
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def walk(value, path):
    if isinstance(value, dict):
        if value.get('coordinates'):
            if not isinstance(value['coordinates'], list):
                raise ValueError('coordinates must be a list: ' + path)
            yield path + '/coordinates', value['coordinates'], path, value
        for key, member in value.items():
            if key not in {'coordinates', 'evidence', 'source_evidence', 'quotes', 'quote', 'confidence'}:
                key = str(key).replace('~', '~0').replace('/', '~1')
                yield from walk(member, path + '/' + key)
    elif isinstance(value, list):
        for i, member in enumerate(value):
            yield from walk(member, path + '/' + str(i))
