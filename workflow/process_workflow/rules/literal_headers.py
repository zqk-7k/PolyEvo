"""Frozen pure rules; batch entry points and dataset constants removed."""
import re
from .headers import header_key

def named_header(text):
    t = header_key(text)
    return bool(re.fullmatch('(?:filler|modifiedblend|blend|material|entry|no\\.?|parts|phr|polyester|glycol|dicarboxylicintermediate|corona|filmthickness(?:\\([^)]*\\))?|extruderscrewspeed(?:\\([^)]*\\))?|[a-z][a-z0-9-]{1,12}/[a-z][a-z0-9-]{1,12})', t))
