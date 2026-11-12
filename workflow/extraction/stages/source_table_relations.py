"""Source-grounded table units and literal specimen variants, within Stage 4.

The caller supplies independently read table-column contexts. No gold or scores
are accepted. Parent specimen identities are never inferred from a numeric value.
"""
from __future__ import annotations
import copy
import re
import unicodedata
from stages.stage4_direct_table_supplement import plain,table_cell_scalar,evidence,canonical_unit,header_applies,power_header
from stages.source_display_scaling import scale_rule

VERSION='1.5.9'


def column_unit(context):
    """Use the printed unit, never replace it with model-generated prose.

    Both source and normalized values still describe the SAME source cell.
    No physical conversion or dimensional inference is performed here.
    """
    raw=context.get('unit_raw')
    if raw is None:raw=context.get('unit_normalized')
    if raw is None:return None
    text=plain(str(raw)).strip()
    # An absent unit in a column reader is an abstention, not evidence that a
    # source-grounded unit from a methods paragraph should be erased.
    if not text:return None
    # A printed power is a display convention, not a unit name. Do not
    # reinterpret the quantity here or replace a correct existing unit with
    # "x10^2". The independent display-scale reader handles such headings.
    if re.search(r'10\s*\^\s*[{(]?[+−-]?\d',text):return None
    def typography(value):
        value=re.sub(r'(?<=[A-Za-z])\.(?=[\s/]|$)','',value.strip())
        return re.sub(r'^\^(?=°)','',value).rstrip('.').strip()
    # Readers can return a whole header such as Yield(%). Retain only its
    # explicitly parenthesized unit, not a property name as a physical unit.
    # Keep a power applied to a complete physical unit, e.g. (cal/ml)^(1/2).
    # The exponent changes its dimension and must not be discarded while
    # trimming a surrounding response name.
    powered=re.search(r'\(([^()]+)\)\s*(?:\^\s*\{?\(?\s*([+-]?\d+\s*/\s*\d+|[+-]?\d+)\s*\)?\}?|([½⅓¼]))\s*$',text)
    if powered:
        exponent=powered[2] or {'½':'1/2','⅓':'1/3','¼':'1/4'}[powered[3]]
        return '('+typography(powered[1])+')^('+re.sub(r'\s+','',exponent)+')'
    parenthesized=re.findall(r'\(([^()]+)\)',text)
    if parenthesized:
        prefix=typography(text.split('(',1)[0])
        # "deg C (dilatometer)" already starts with a unit. The trailing
        # parenthesis describes a method, not a replacement physical unit.
        known={'°c','°k','k','dl/g','g/cc','g/cm3','g/cm^3','%','psi'}
        text=prefix if prefix.casefold() in known else parenthesized[-1]
    text=typography(text)
    aliases={'deciliter per gram':'dL/g','decilitre per gram':'dL/g',
             'degree celsius':'°C','degrees celsius':'°C',
             'degree kelvin':'K','degrees kelvin':'K',
             'percent':'%','percentage':'%','degrees':'degree','deg':'degree',
             '°k':'K','°c':'°C','dl/g':'dL/g','g/cc':'g/cm3',
             '% of original':'%'}
    text=aliases.get(text.casefold(),text)
    return canonical_unit(text)

def norm(s):
    text=unicodedata.normalize('NFKC',plain(s)).casefold()
    for name,symbol in [('delta','δ'),('eta','η'),('alpha','α'),('lambda','λ')]:
        text=text.replace('\\'+name,symbol)
    return re.sub(r'[\W_]','',text)

def witness(w,blocks):
    block=blocks.get(w.get('block_id'))
    if not block:return None
    q=w.get('quote','')
    raw=block.get('text') or block.get('table_body') or ''
    if not q or norm(q) not in norm(raw):return None
    if q not in raw and re.search(r'\d',q):
        # The text-label equivalence above removes punctuation. That is unsafe
        # for numerical witnesses: -0.5 is NOT +0.5, and 1.6 is NOT 16.
        # Permit only harmless text rendering/whitespace differences here;
        # retain decimal points, signs, ranges and mathematical operators.
        def numeric_literal(text):
            text=unicodedata.normalize('NFKC',plain(text)).replace('−','-')
            return re.sub(r'\s+','',text).casefold()
        if numeric_literal(q) not in numeric_literal(raw):return None
    # A model may render Tg where the source spells T_{g}. Preserve an ACTUAL
    # source substring for publication validation, not the model's rendering.
    # The complete source block is retained only when literal snapping is needed.
    literal=q if q in raw else raw
    return {'block_id':block['block_id'],'page':block['page'],'bbox':block.get('bbox'),
            'source_type':block['type'],'source_sentence':literal,'table_locator':None}

def entries(doc):
    for r in doc.get('properties',[]):yield r,None,r['property_id']
    for s in doc.get('property_series',[]):
        for p in s['points']:yield p,s,s['series_id']+':'+p['point_id']


def row_response_units(table, column_index):
    """Explicit property-row unit declarations, not numeric specimen axes."""
    known={'°c','k','g/mol','g/cm3','g/cm3','mpa','gpa','pa','pa·s','pa.s',
           'pa*s','j/g','g/10min','n·m','n.m','%','s','min','h','dl/g','psi',
           'mm','nm','um','µm','μm','cm-1','mjm-2','mj/m2','j/m2'}
    declarations={}
    rows={c['row_index'] for c in table.get('table_cells',[])}
    for row_index in rows:
        left=sorted((c for c in table['table_cells'] if c['row_index']==row_index
                    and c['column_index']<column_index),key=lambda c:c['column_index'])
        if not left:continue
        first=plain(left[0]['text']).strip()
        if not first or re.match(r'^[+−-]?\d',first):continue
        for c in left:
            surface=plain(c['text']).strip()
            candidates=re.findall(r'\(([^()]+)\)',surface)
            # Printed property/unit notation also uses a slash or comma, e.g.
            # Young's modulus/MPa, tau_1/2/s, and Tensile strength, psi.
            # Try complete suffixes, so g/10 min remains one physical unit.
            candidates.extend(surface[m.end():] for m in re.finditer(r'[/,]',surface))
            # A separate unit column is valid only AFTER the property label.
            if c is not left[0]:candidates.append(surface)
            unit=next((u for token in candidates
                       if (u:=column_unit({'unit_raw':token})) and u.casefold() in known),None)
            if unit:
                declarations[row_index]={'unit':unit,'cell':c,'label':first};break
    return declarations

def apply_table_relations(stage3,stage4,stage0,column_contexts,*,specimen_links=()):
    s3,s4=copy.deepcopy(stage3),copy.deepcopy(stage4)
    blocks={b['block_id']:b for b in stage0['elements']}
    samples={s['sample_id']:s for s in s3['samples']}
    columns={};rejected=[];changes=[];row_units_cache={}
    for c in column_contexts:
        table=blocks.get(c.get('table_id'))
        proof=[witness(w,blocks) for w in c.get('evidence',[])]
        if not table or table['type']!='table' or not proof or any(p is None for p in proof):
            rejected.append({'table_id':c.get('table_id'),'column_index':c.get('column_index'),'reason':'ungrounded column interpretation'});continue
        c={**c,'verified_evidence':proof}
        columns[c['table_id'],int(c['column_index'])]=c
    variants={};next_id=max([int(s[1:]) for s in samples]+[0])+1
    for r,parent,rid in entries(s4):
        locators=[]
        for ev in r.get('evidence',[]):
            loc=ev.get('table_locator') or {};table=blocks.get(ev.get('block_id'))
            if not table or table['type']!='table':continue
            cell=next((c for c in table.get('table_cells',[]) if c['cell_id']==loc.get('cell_id')),None)
            if not cell:continue
            try:value=table_cell_scalar(r.get('value_raw',''))
            except Exception:continue
            if value is None or value!=table_cell_scalar(cell['text']):continue
            locators.append((table,cell,loc))
        unique={(t['block_id'],c['cell_id']) for t,c,_ in locators}
        if len(unique)!=1:continue
        table,cell,loc=locators[0]
        orientation_key=(table['block_id'],cell['column_index'])
        if orientation_key not in row_units_cache:
            row_units_cache[orientation_key]=row_response_units(table,cell['column_index'])
        response_rows=row_units_cache[orientation_key]
        transposed=len(response_rows)>=2
        response_row=response_rows.get(cell['row_index']) if transposed else None
        context=columns.get((table['block_id'],cell['column_index']))
        if transposed:
            # Sample columns can contain torque, viscosity and melt-index rows.
            # One column-wide unit/method cannot describe all those properties.
            # Derive a row's unit only from its literal declaration. An absent
            # row declaration is not permission to borrow another row's unit.
            proof=[]
            if response_row:
                header=response_row['cell']
                proof=[evidence({'table_id':table['block_id'],'page':table['page'],'bbox':table.get('bbox')},
                    header,row_label=response_row['label'],column_label=header['text'])]
            context={'unit_raw':response_row['unit'] if response_row else None,
                     'conditions':{},'verified_evidence':proof} if response_row else None
        if context:
            unit=column_unit(context)
            if unit is not None:
                current=r.get('unit_raw') or r.get('unit_normalized') or (parent or {}).get('unit_raw') or (parent or {}).get('unit_normalized')
                if canonical_unit(current)!=canonical_unit(unit):
                    r['unit_raw']=unit or None;r['unit_normalized']=unit or None
                    changes.append({'record_id':rid,'kind':'source_table_unit','before':current,'after':unit,'proof':context['verified_evidence']})
                    for e in context['verified_evidence']:
                        if e not in r['evidence']:r['evidence'].append(e)
            cc=context.get('conditions',{})
            if cc:
                mc=r.setdefault('measurement_context',{'condition_status':'reported','other_conditions':{}})
                mc['condition_status']='reported';mc.setdefault('other_conditions',{});mc.setdefault('other_condition_evidence',{})
                for k,v in cc.items():
                    if k not in {'atmosphere','crystallization_state','measurement_temperature','pressure',
                                 'weight_loss_criterion','heating_rate','method','frequency','transition_branch'} or v is None:continue
                    v=str(v)
                    key='source_'+k
                    if mc['other_conditions'].get(key)!=v:
                        mc['other_conditions'][key]=v;mc['other_condition_evidence'][key]=context['verified_evidence']
                        changes.append({'record_id':rid,'kind':'source_table_condition','field':k,'after':v})
        # Keep distinguishing source column labels (TgU versus TgL, T5 versus
        # T10, heating scans) in the relation, not just its generic property code.
        numeric_rows=[c['row_index'] for c in table['table_cells'] if c['column_index']==cell['column_index'] and table_cell_scalar(c['text']) is not None]
        boundary=min(numeric_rows) if numeric_rows else cell['row_index']
        headers=[h for h in table['table_cells'] if h['row_index']<boundary and header_applies(h,cell) and plain(h['text'])]
        headers=[h for h in headers if not re.fullmatch(r'homopolymers?|copolymers?|blends?|ipns?',plain(h['text']),re.I)]
        kelvin=[h for h in headers if re.search(r'\b(?:degree\s+Kelvin|Kelvin)\b',plain(h['text']),re.I)]
        if kelvin and canonical_unit(r.get('unit_raw') or (parent or {}).get('unit_raw'))!='K':
            before=r.get('unit_raw');r['unit_raw']='K';r['unit_normalized']='K'
            proof=[evidence({'table_id':table['block_id'],'page':table['page'],'bbox':table.get('bbox')},h,row_label='source header',column_label=h['text']) for h in kelvin]
            r['evidence'].extend(e for e in proof if e not in r['evidence'])
            changes.append({'record_id':rid,'kind':'literal_kelvin_unit','before':before,'after':'K','proof':proof})
        # Literal unit multipliers BEFORE M_n/M_w, unlike Q*10^n, denote
        # the displayed molecular-weight unit. Never use polymer plausibility.
        factors=[]
        for h in headers:
            text=re.sub(r'\s+','',power_header(h['text'])).replace('\\','')
            m=re.match(r'^10\^([1-9])M_?[nwzv](?![A-Za-z])',text,re.I)
            if m:factors.append(10**int(m[1]))
            rule=scale_rule(h['text'])
            if rule and re.search(r'M_?[nwzv]',text,re.I):factors.append(rule[0])
        if factors and len(set(factors))==1:
            factor=factors[0];literal=table_cell_scalar(cell['text'])
            if literal is not None and table_cell_scalar(r.get('value_raw',''))==literal:
                value=literal*factor;r['value_raw']=format(value,'.12g');r['value_min']=value;r['value_max']=value
                r['unit_raw']='g/mol';r['unit_normalized']='g/mol'
                changes.append({'record_id':rid,'kind':'explicit_molecular_mass_multiplier','source_cell':cell['text'],'factor':factor,'after':value})
        label=(response_row['label'] if response_row else
               ' | '.join(dict.fromkeys(plain(h['text']) for h in headers)))
        if label:
            mc=r.setdefault('measurement_context',{'condition_status':'reported','other_conditions':{}})
            mc.setdefault('other_conditions',{});mc.setdefault('other_condition_evidence',{})
            if mc['other_conditions'].get('source_response_header')!=label:
                mc['other_conditions']['source_response_header']=label;mc['condition_status']='reported'
                label_sources=[response_row['cell']] if response_row else headers
                mc['other_condition_evidence']['source_response_header']=[evidence({'table_id':table['block_id'],'page':table['page'],'bbox':table.get('bbox')},h,row_label='source header',column_label=h['text']) for h in label_sources]
                changes.append({'record_id':rid,'kind':'source_response_header','after':label})
        # Split only a literal composition-qualified extension of an already
        # identified parent. A bare numeric row code cannot identify a polymer.
        sid=r.get('sample_id') or (parent or {}).get('sample_id');sample=samples.get(sid)
        if not sample:continue
        row_cells=[c for c in table['table_cells'] if c['row_index']==cell['row_index'] and c['column_index']<cell['column_index']]
        label_cells=[c for c in row_cells if re.match(r'^\s*\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?\s+[A-Za-z]',plain(c['text']))]
        label=next((c for c in label_cells if any(norm(alias) in norm(c['text']) for alias in [sample.get('sample_label_raw'),sample.get('polymer_name')] if alias)),None)
        if label is None or norm(sample.get('sample_label_raw'))==norm(label['text']):continue
        key=(sid,label['text'])
        if key not in variants:
            new=copy.deepcopy(sample);new['sample_id']=f's{next_id:03d}';next_id+=1
            new['sample_label_raw']=plain(label['text']);new['polymer_name']=sample['polymer_name']+' ['+plain(label['text'])+']'
            new['sample_kind']='test_specimen'
            new['evidence']=evidence({'table_id':table['block_id'],'page':table['page'],'bbox':table.get('bbox')},label,row_label=label['text'],column_label='source specimen label')
            new['state_description']='Source-defined composition specimen; parent identity '+sid
            s3['samples'].append(new);samples[new['sample_id']]=new;variants[key]=new['sample_id']
        r['sample_id']=variants[key]
        if 'sample_resolution_status' in r:r['sample_resolution_status']='resolved'
        changes.append({'record_id':rid,'kind':'composition_sample_binding','parent_sample_id':sid,'sample_id':r['sample_id'],'source_label':label['text']})
    from stages.source_specimen_links import apply_specimen_links
    s3,s4,specimen_audit=apply_specimen_links(s3,s4,stage0,specimen_links)
    changes.extend(specimen_audit['changes'])
    from stages.source_scalar_consistency import repair_scalar_bounds
    s4,scalar_audit=repair_scalar_bounds(s4,stage0)
    changes.extend(scalar_audit['changes'])
    return s3,s4,{'version':VERSION,'gold_access':False,'changes':changes,'rejected_interpretations':rejected,
                  'new_source_specimens':len(variants),'cross_table_specimen_links':specimen_audit,
                  'source_scalar_bounds':scalar_audit}
