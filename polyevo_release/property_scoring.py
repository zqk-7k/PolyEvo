"""Pure aggregation of completed relation judgements. No model or network imports."""
from collections import defaultdict


def maximum_matching(rows):
    edges = {r['id']: sorted(set(r.get('eligible_reference_matches', []))) for r in rows}
    owners = {}
    def visit(pid, seen):
        for gid in edges[pid]:
            if gid in seen: continue
            seen.add(gid)
            if gid not in owners or visit(owners[gid], seen):
                owners[gid] = pid
                return True
        return False
    for pid in sorted(edges): visit(pid, set())
    return owners


def aggregate(ledger, gold, cohort):
    """Same closed-reference arithmetic as archived evaluation, with ID guards."""
    if len(cohort) != len(set(cohort)):
        raise ValueError('Duplicate cohort paper')
    by_ref = {r: [] for r in cohort}
    reference = {g['id']: g for g in gold}
    if len(reference) != len(gold): raise ValueError('Duplicate reference ID')
    if any(g['reference_no'] not in by_ref for g in gold): raise ValueError('Foreign reference paper')
    eligible = {g['id'] for g in gold if g['status'] == 'eligible'}
    excluded = set(reference) - eligible
    ids = set()
    for row in ledger:
        if row['id'] in ids: raise ValueError('Duplicate prediction ID')
        ids.add(row['id'])
        if row['reference_no'] not in by_ref: raise ValueError('Foreign prediction paper')
        if row['status'] not in {'supported', 'contradicted', 'unresolved', 'out_of_scope'}:
            raise ValueError('Invalid source audit status')
        if type(row.get('reference_scope')) is not bool: raise ValueError('Explicit scope decision required')
        matches = row.get('eligible_reference_matches', [])
        if matches and row['status'] != 'supported': raise ValueError('Only supported records can match')
        for gid in matches:
            if gid not in eligible or reference[gid]['reference_no'] != row['reference_no']:
                raise ValueError('Foreign or ineligible reference match')
        by_ref[row['reference_no']].append(row)
    per = []
    pairs = []
    for ref in cohort:
        rows = by_ref[ref]
        gs = {g['id'] for g in gold if g['reference_no'] == ref and g['status'] == 'eligible'}
        owned = maximum_matching(rows)
        assigned = set(owned.values())
        fp = unknown = duplicates = 0
        for row in rows:
            hits = set(row.get('eligible_reference_matches', [])) & gs
            if hits:
                if row['id'] not in assigned: duplicates += 1
            elif row['status'] == 'out_of_scope': continue
            elif row['reference_scope']:
                original = row.get('matched_reference_ids', [])
                # Only same-paper excluded facts justify a closed-task exclusion.
                if original and set(original) <= excluded and all(reference[g]['reference_no'] == ref for g in original):
                    continue
                if row['status'] in {'supported', 'unresolved'}: unknown += 1
                else: fp += 1
        tp = len(owned)
        per.append({'reference_no': ref, 'gold': len(gs), 'tp': tp, 'fn': len(gs)-tp,
                    'fp': fp, 'unresolved_in_scope': unknown, 'duplicate_reference_hits': duplicates,
                    'records_audited': len(rows)})
        pairs.extend({'reference_no': ref, 'reference_id': g, 'prediction_id': p} for g, p in owned.items())
    total = {k: sum(p[k] for p in per) for k in ('gold','tp','fn','fp','unresolved_in_scope',
                                               'duplicate_reference_hits','records_audited')}
    tp, fn, fp, u = (total[k] for k in ('tp','fn','fp','unresolved_in_scope'))
    total.update(precision_confirmed=tp/(tp+fp+u) if tp+fp+u else None,
                 recall_confirmed=tp/total['gold'] if total['gold'] else None,
                 f1_confirmed=2*tp/(2*tp+fn+fp+u) if 2*tp+fn+fp+u else None,
                 papers=len(cohort), expert_gold=False)
    return {'metrics': total, 'papers': per, 'matched_pairs': pairs,
            'semantic_judgements_created': False, 'goal_complete': False}
