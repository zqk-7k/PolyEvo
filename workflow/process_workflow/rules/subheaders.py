"""Frozen pure rules; batch entry points and dataset constants removed."""
import re, html, unicodedata

def key(text):
    t = unicodedata.normalize('NFKC', html.unescape(str(text))).lower()
    t = re.sub('\\\\(?:mathrm|text|mathit)\\s*', '', t)
    return re.sub('[\\s${}_^\\\\]+', '', t).strip('()[]')

UNIT = '(?:mol(?:es?|e)?/l|mol(?:es?|e)?l[-−]?1|mmol(?:e)?|ml|g/dl|g/l|dl/g|wt%|mol%|%|°c|k|hr\\.?|min\\.?|h|s)'

def plausible_unit_or_named_subheader(text):
    t = key(text)
    if re.fullmatch(UNIT + '(?:[.,]?(?:×|x|times)10[-−]?\\d+)?', t):
        return True
    t = t.replace('tempera-ture', 'temperature').replace('react-ant', 'reactant')
    return bool(re.fullmatch('(?:nmp|pyridine|reactant|solvent|temperature|time|volume|concentration)[,:(]+' + UNIT + '[).:]*', t))

def covers(c, row, col):
    return c['row_index'] <= row < c['row_index'] + int(c.get('row_span', 1)) and c['column_index'] <= col < c['column_index'] + int(c.get('column_span', 1))
