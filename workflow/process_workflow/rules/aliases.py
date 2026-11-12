"""Frozen pure rules; batch entry points and dataset constants removed."""
import re, html, unicodedata

def norm(value):
    return re.sub('\\s+', '', unicodedata.normalize('NFKC', html.unescape(str(value))))

def pair(text):
    text = str(text).replace('\\', '').replace('$', '')
    hits = re.findall('(?<![A-Za-z0-9])([A-Z][A-Z0-9-]{1,12})\\s*/\\s*([A-Z][A-Z0-9-]{1,12})(?![A-Za-z0-9])', text)
    return set(hits)

def numeric_ratio(text):
    m = re.fullmatch('\\s*(\\d+(?:\\.\\d+)?)\\s*/\\s*(\\d+(?:\\.\\d+)?)\\s*', str(text))
    return m.groups() if m else None
