"""Distinguish an explicitly defined loss temperature from an onset claim."""
import copy
import re
from stages.stage4_direct_table_supplement import plain, canonical_unit

VERSION='1.0.0'


def repair_loss_temperature_meaning(stage4, stage0):
    out=copy.deepcopy(stage4)
    blocks={b['block_id']:b for b in stage0.get('elements',[])}
    rows=[(r,r,r['property_id']) for r in out.get('properties',[])]
    rows += [(p,s,s['series_id']+':'+p['point_id'])
             for s in out.get('property_series',[]) for p in s.get('points',[])]
    changes=[]
    for row,parent,rid in rows:
        name=row.get('property_name_normalized') or parent.get('property_name_normalized') or ''
        if not re.search(r'onset',name,re.I):continue
        if not re.search(r'decompos|degrad|thermal',name,re.I):continue
        unit=row.get('unit_raw') or parent.get('unit_raw') or row.get('unit_normalized') or parent.get('unit_normalized')
        if canonical_unit(unit) not in {'°C','K'}:continue
        mc=row.get('measurement_context') or {}
        oc=mc.get('other_conditions') or {}
        criterion=oc.get('weight_loss_threshold_percent')
        if not isinstance(criterion,str) or not re.fullmatch(r'\d+(?:\.\d+)?',criterion):continue
        proofs=(mc.get('other_condition_evidence') or {}).get('weight_loss_threshold_percent',[])
        verified=[]
        for proof in proofs:
            block=blocks.get(proof.get('block_id'),{})
            literal=proof.get('source_sentence') or ''
            source=block.get('text') or block.get('table_body') or ''
            if not literal or literal not in source:continue
            text=plain(literal)
            pattern=re.escape(criterion)+r'\s*%\s*(?:weight|mass)\s*[- ]*loss\s*temperature'
            if re.search(pattern,text,re.I):verified.append(proof)
        if not verified:continue
        before={k:row.get(k) for k in ('property_name_raw','property_name_normalized')}
        original=row.get('property_name_raw') or parent.get('property_name_raw') or ''
        row['property_name_raw']='Temperature at '+criterion+'% weight loss'
        row['property_name_normalized']='thermal_decomposition_temperature'
        mc['other_conditions']['source_criterion_original_response_label']=original
        mc['other_conditions']['source_response_definition']='Source defines a fixed weight-loss temperature, not an onset'
        mc.setdefault('other_condition_evidence',{})['source_response_definition']=copy.deepcopy(verified)
        for proof in verified:
            if proof not in row.setdefault('evidence',[]):row['evidence'].append(proof)
        changes.append({'record_id':rid,'before':before,
            'after':{k:row.get(k) for k in before},'proof':verified})
    return out,{'version':VERSION,'changes':changes,'reference_answers_loaded':False,
                'quantities_changed':False,'process_content_changed':False}
