"""Apply source-grounded measurement corrections without reading evaluation labels.

Replacing a shared context for one observation creates an isolated condition ID,
so unrelated measurements retain their original conditions. Raw proposals and
previous context values are returned to the caller for archival.
"""
import copy

from schema.polymer_schema import MeasurementContext, MeasurementCondition
from stages.source_table_relations import witness


def apply_measurement_corrections(stage4, stage0, proposals):
    result = copy.deepcopy(stage4)
    blocks = {b['block_id']: b for b in stage0['elements']}
    targets = {r['property_id']: r for r in result.get('properties', [])}
    targets.update({s['series_id']: s for s in result['property_series']})
    targets.update({s['series_id']+':'+p['point_id']: p for s in result['property_series'] for p in s['points']})
    targets.update({r['property_id']: r for r in result.get('specialized_properties', [])})
    existing = result['measurement_conditions']
    next_id = max([int(c['condition_id'][2:]) for c in existing] or [0]) + 1
    changes, rejected = [], []
    allowed = {'temperature', 'frequency', 'humidity', 'pressure', 'wavelength',
               'other_conditions', 'other_condition_evidence', 'condition_status'}
    for proposal in proposals:
        uid = proposal.get('record_id')
        context = proposal.get('context')
        proofs = [witness(w, blocks) for w in proposal.get('evidence', [])]
        if uid not in targets or not isinstance(context, dict) or not set(context)<=allowed or not proofs or any(p is None for p in proofs):
            rejected.append({'id': uid, 'reason': 'unknown target, invalid fields, or ungrounded evidence'})
            continue
        context = copy.deepcopy(context)
        # Evidence is supplied by the host, never trusted as generated metadata.
        context['other_condition_evidence'] = {k: proofs for k in context.get('other_conditions', {})}
        try:
            verified = MeasurementContext.model_validate(context).model_dump(exclude_none=True)
        except ValueError:
            rejected.append({'id': uid, 'reason': 'invalid native measurement context'})
            continue
        row = targets[uid]
        before = copy.deepcopy(row)
        condition_id = None
        if 'measurement_condition_id' in row:
            condition_id = f'mc{next_id:03d}'
            next_id += 1
            condition = {k: v for k, v in verified.items() if k!='other_condition_evidence_ids'}
            condition.update(condition_id=condition_id, evidence=proofs[0], confidence=row.get('confidence'))
            existing.append(MeasurementCondition.model_validate(condition).model_dump(exclude_none=True))
            row['measurement_condition_id'] = condition_id
        row['measurement_context'] = verified
        if 'points' in row:
            # Remove stale copies of a disproven COMMON condition from children,
            # while preserving every point-specific value that differed from it.
            old_common = (before.get('measurement_context') or {}).get('other_conditions', {})
            new_common = verified.get('other_conditions', {})
            for point in row['points']:
                local = point.get('measurement_context')
                if not local:
                    continue
                own = local.get('other_conditions', {})
                for key, old_value in old_common.items():
                    if key in own and own[key] == old_value and new_common.get(key) != old_value:
                        if key in new_common:
                            own[key] = new_common[key]
                            local.setdefault('other_condition_evidence', {})[key] = proofs
                        else:
                            own.pop(key)
                            local.get('other_condition_evidence', {}).pop(key, None)
                has_quantity = any(local.get(k) is not None for k in ('temperature','frequency','humidity','pressure','wavelength'))
                local['condition_status'] = 'reported' if own or has_quantity else 'not_reported'
        method = proposal.get('determination_method_raw')
        if method is not None:
            if not isinstance(method, str) or not method.strip():
                rejected.append({'id': uid, 'reason': 'invalid method definition'})
            else:
                row['determination_method_raw'] = method
                if 'point_id' in row:
                    # Keep the explicit point-local method, as well as its
                    # auditable context. A shared series method is not changed.
                    row['measurement_context']['other_conditions']['method'] = method
                    row['measurement_context']['other_condition_evidence']['method'] = proofs
                    row['measurement_context']['condition_status'] = 'reported'
        for proof in proofs:
            if proof not in row['evidence']:
                row['evidence'].append(proof)
        changes.append({'id': uid, 'before': before, 'after_context': verified,
                        'isolated_condition_id': condition_id, 'evidence': proofs,
                        'reason': proposal.get('reason')})
    return result, {'changes': changes, 'rejected': rejected, 'records_deleted': 0}
