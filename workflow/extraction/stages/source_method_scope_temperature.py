"""Do not attach an explicitly tensile-only temperature to an impact test.

This corrects a misplaced measurement qualifier, not a specimen state. The
original assertion and source witness are retained in the returned audit.
"""
import copy
import re
from stages.source_table_relations import witness
from stages.stage4_direct_table_supplement import plain

VERSION = '1.0.0'
IMPACT = {'izod_impact','charpy_impact','impact_strength','notched_impact_strength'}


def repair(stage4, stage0):
    result=copy.deepcopy(stage4);changes=[]
    blocks={b['block_id']:b for b in stage0['elements']}
    source_text=[plain(b.get('text') or b.get('table_body') or '') for b in blocks.values()]

    def targeted_context(context, prop, method, rid):
        temperature=context.get('temperature')
        if prop not in IMPACT or not isinstance(temperature,dict): return
        own_method=' '.join([method,str(context.get('other_conditions',{}).get('source_method','')),
                             str(context.get('other_conditions',{}).get('test_standard',''))])
        if not re.search(r'D\s*[-–]?\s*256\b',own_method,re.I): return
        # Require the source itself to identify the impact method; neither a
        # property vocabulary nor an inherited context constitutes that proof.
        if not any(re.search(r'notched\s+impact',t,re.I) and re.search(r'D\s*[-–]?\s*256\b',t,re.I)
                   for t in source_text): return
        proofs=temperature.get('evidence') or []
        if not proofs: return
        verified=[]
        for proof in proofs:
            quote=proof.get('source_sentence') or '';text=plain(quote)
            if not re.match(r'(?:The\s+)?[Tt]ensile\s+(?:test|tests)\b',text): return
            if not re.search(r'D\s*[-–]?\s*638\b',text,re.I) or re.search(r'impact',text,re.I): return
            verified_proof=witness({'block_id':proof.get('block_id'),'quote':quote},blocks)
            if verified_proof is None: return
            verified.append(verified_proof)
        # An explicit common protocol or impact temperature takes precedence.
        # In that situation this narrow correction must abstain.
        for text in source_text:
            for sentence in re.split(r'(?<=[.!?])\s+',text):
                subject=(r'impact\s+(?:strength\s+)?(?:test|tests|measurement|measurements)\b'
                         r'[^.;]{0,90}(?:\bat\b[^.;]{0,25}(?:°\s*C|\\circ|room\s+temp)|temperature)')
                common=r'all\s+(?:the\s+)?tests\b[^.;]{0,90}(?:°\s*C|\\circ|temperature|room\s+temp)'
                if re.search(subject,sentence,re.I) or re.search(common,sentence,re.I):
                    return
        before=copy.deepcopy(temperature);context.pop('temperature')
        changes.append({'record_id':rid,'removed_misassigned_field':'temperature','before':before,
            'source_scope':'tensile test (ASTM D638), not impact test (ASTM D256)',
            'proof':verified,'source_defined_specimen_states_changed':False})

    for row in result.get('properties',[]):
        targeted_context(row.get('measurement_context') or {},row.get('property_name_normalized'),
                         row.get('determination_method_raw',''),row['property_id'])
    for series in result.get('property_series',[]):
        prop=series.get('property_name_normalized');method=series.get('determination_method_raw','')
        targeted_context(series.get('measurement_context') or {},prop,method,series['series_id'])
        for point in series['points']:
            targeted_context(point.get('measurement_context') or {},point.get('property_name_normalized') or prop,
                point.get('determination_method_raw') or method,series['series_id']+':'+point['point_id'])
    return result,{'version':VERSION,'changes':changes,'reference_answers_loaded':False,
                   'processes_samples_values_units_changed':False}
