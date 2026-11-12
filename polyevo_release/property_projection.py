"""Frozen pure property projection. No transport imports or inference."""
from __future__ import annotations
import math
import re
import html
from typing import Any

_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"

def scientific_literal(surface: str) -> float | None:
    text=str(surface).replace('\\times','×')
    supers='⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻'
    table=str.maketrans(supers,'0123456789+-')
    text=re.sub(r'10(['+supers+r']+)',lambda m:'10^'+m[1].translate(table),text)
    text=re.sub(r'\s+','',text).replace('{','').replace('}','').replace('$','')
    match=re.fullmatch(r'([+-]?(?:\d+(?:\.\d*)?|\.\d+))[×x·]10\^([+-]?\d+)',text)
    if not match:return None
    mantissa=float(match[1]);exponent=int(match[2])
    if abs(exponent)>308:return None
    value=mantissa * 10.**exponent
    if not math.isfinite(value) or (value==0 and mantissa!=0):return None
    return value

def plain(value: Any) -> str:
    text = html.unescape(str(value or ""))
    # OCR may wrap a printed unit in an empty-denominator layout fraction.
    # Remove that wrapper only; real fractions retain their denominator.
    text = re.sub(r'\\frac\s*\{([^{}]*)\}\s*\{\s*\}', r'\1', text)
    # Preserve printed superscript exponents before removing HTML markup.
    text = re.sub(r"<sup>\s*([+-]?\d+)\s*</sup>", r"^\1", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\\(?:text|mathrm|textrm|overline|bar)\s*\{([^{}]*)\}", r"\1", text)
    text = text.replace("\\cdot", "·").replace("\\eta", "η").replace("\\theta", "θ")
    text = text.replace("\\circ", "°").replace("\\mu", "μ").replace("\\AA", "Å")
    return re.sub(r"\s+", " ", text.replace("$", "").replace("{", "").replace("}", "")).strip()

def scalar(surface: str) -> float | None:
    text = plain(surface).replace("−", "-").replace("–", "-")
    text = re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", text)
    match = re.fullmatch(rf"\s*({_NUMBER})(?:\s*(?:±|\\pm)\s*{_NUMBER})?\s*", text)
    if not match:
        return scientific_literal(text)
    value = float(match.group(1))
    return value if math.isfinite(value) else None

def table_cell_scalar(surface: str) -> float | None:
    """Full-cell thousands typography, never used by the prose parser."""
    text=plain(surface)
    approximate = re.fullmatch(rf'(?:~|≈|\\sim|\\approx)\s*({_NUMBER})', text)
    if approximate:
        return scalar(approximate[1])
    if re.fullmatch(r'[+−-]\s+\d+(?:\.\d+)?', text):
        return scalar(re.sub(r'\s+', '', text))
    if re.fullmatch(rf'—{_NUMBER}', text):
        return scalar('-' + text[1:])
    if re.fullmatch(r'[+-]?\d{1,3}(?:\s+\d{3})+(?:\.\d+)?',text):
        return scalar(re.sub(r'\s+','',text))
    return scalar(surface)

def quantity_view(row, parent=None):
    parent = parent or {}
    raw_unit = row.get('unit_raw') or parent.get('unit_raw')
    normalized_unit = row.get('unit_normalized') or parent.get('unit_normalized')
    lower, upper = row.get('value_min'), row.get('value_max')
    if raw_unit and normalized_unit and raw_unit != normalized_unit and lower is not None:
        source_scalar = table_cell_scalar(str(row.get('value_raw') or ''))
        if source_scalar is not None and upper == lower:
            # Equal native bounds denote one scalar, not a printed range. Retain
            # its original precision and express the redundant bound in the SAME
            # source unit. Both normalized bounds remain in the native archive.
            return {'value':row['value_raw'], 'value_max':source_scalar, 'unit':raw_unit,
                    'representation':'coherent_source_scalar',
                    'source_value_raw':row['value_raw'], 'source_unit_raw':raw_unit}
        return {'value':format(lower,'.12g'), 'value_max':upper,
                'unit':normalized_unit, 'representation':'normalized_physical_quantity',
                'source_value_raw':row.get('value_raw'), 'source_unit_raw':raw_unit}
    return {'value':row.get('value_raw',lower), 'value_max':upper,
            'unit':raw_unit or normalized_unit or '', 'representation':'source_quantity',
            'source_value_raw':row.get('value_raw'), 'source_unit_raw':raw_unit}

def records(doc):
    """All structured numerical response containers, including specialized IDs."""
    samples={s['sample_id']:s for s in doc.get('samples',[])}
    entities={s['entity_id']:s for s in doc.get('polymer_entities',[])}
    conditions={c['condition_id']:c for c in doc.get('measurement_conditions',[])}
    evidence={e['evidence_id']:e for e in doc.get('evidence',[])}
    rows=[]
    def emit(row,parent,kind,rid):
        sid=row.get('sample_id') or parent.get('sample_id')
        specimen=samples.get(sid,{})
        ent=entities.get(row.get('entity_id') or specimen.get('refers_to_entity') or parent.get('entity_id'),{})
        mc=conditions.get(row.get('measurement_condition_id') or parent.get('measurement_condition_id'),{})
        subject={k:v for k,v in specimen.items() if k not in {'confidence','evidence_ids'}}
        subject['entity']={k:v for k,v in ent.items() if k in {'polymer_name','source_names','polymer_type'}}
        subject['coordinates']=row.get('coordinates',[])
        if row.get('sample_label_raw'):subject['sample_label_raw']=row['sample_label_raw']
        prop=row.get('property_name_normalized') or row.get('property_name_raw') or parent.get('property_name_normalized') or parent.get('property_name_raw')
        if kind=='specialized':
            prop=prop or row.get('semantic_label') or row.get('source_field')
            if row.get('variant'):prop=f"{prop} ({row['variant']})"
        raw_label=row.get('property_name_raw') or parent.get('property_name_raw')
        if raw_label and raw_label!=prop:
            # Raw phase/criterion/branch qualifiers are EMITTED scientific content,
            # not inferred from a source quote. Never hide them behind a taxonomy label.
            prop=f"{prop} [source label: {raw_label}]"
        quantity=quantity_view(row,parent)
        ids=list(dict.fromkeys(row.get('evidence_ids',[])+parent.get('evidence_ids',[])))
        rows.append({'source_record_id':rid,'kind':kind,'material':subject,'property':prop,
                     'value':quantity['value'],'value_max':quantity['value_max'],'unit':quantity['unit'],
                     'method':row.get('determination_method_raw') or row.get('method_raw') or parent.get('determination_method_raw') or mc.get('method_raw') or mc.get('method_normalized',''),
                     'conditions':{'linked':mc,'record':row.get('measurement_context',{}),'series':parent.get('measurement_context',{})},
                     'evidence':[evidence[e] for e in ids if e in evidence],
                     'resolution_status':row.get('sample_resolution_status') or parent.get('sample_resolution_status'),
                     'publication_status':row.get('publication_status') or parent.get('publication_status') or 'implicit_final_container'})
    for row in doc.get('property_observations',[]):emit(row,{},'property',row['property_id'])
    for series in doc.get('property_series',[]):
        for point in series.get('points',[]):emit(point,series,'series_point',series['series_id']+':'+point['point_id'])
    for row in doc.get('specialized_property_observations',[]):
        emit(row,{},'specialized',row.get('specialized_id') or row.get('property_id'))
    ids=[r['source_record_id'] for r in rows]
    if not all(ids) or len(ids)!=len(set(ids)):raise RuntimeError('Missing or duplicate native scientific IDs')
    return rows

