"""Frozen pure rules; batch entry points and dataset constants removed."""
import re, html, unicodedata

def explicit_named_unit(text):
    t = unicodedata.normalize('NFKC', html.unescape(text))
    t = re.sub('\\\\(?:mathrm|text|mathit)\\s*', '', t)
    t = re.sub('[${}^_\\\\]', '', t).strip()
    return bool(re.fullmatch('[A-Za-z][A-Za-z0-9 ,./–−-]*\\s*\\(\\s*(?:[mMμu]?L|[mμu]?g|mmol|mol|mol/L|mol/l|wt\\s*%|mol\\s*%|%|phr|°C|K|h|hr|min|s)\\s*\\)', t))
