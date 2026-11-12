"""Recompute manuscript scores from the preserved scientific decisions."""
from __future__ import annotations
import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from polyevo_release.property_scoring import aggregate

def csvrows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def jsonrows(path):
    with path.open(encoding='utf-8') as f:
        for line in f:
            if line.strip():yield json.loads(line)

def save(path, rows):
    rows=list(rows);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def check(actual,expected,label,tol=1e-8):
    if not math.isclose(float(actual),float(expected),rel_tol=tol,abs_tol=tol):
        raise ValueError(f'{label}: reproduced {actual}, expected {expected}')

def relationships(data,out):
    folder=data/'development/relationships'
    ledger=list(jsonrows(folder/'decisions.jsonl'));gold=list(jsonrows(folder/'reference.jsonl'))
    result=aggregate(ledger,gold,sorted({r['reference_no'] for r in ledger}))
    expected={r['metric']:r['value'] for r in csvrows(folder/'expected_metrics.csv')}
    for key,value in expected.items():check(result['metrics'][key],value,key)
    save(out/'development_relationships.csv',[dict(metric=k,value=v) for k,v in result['metrics'].items()])
    save(out/'development_relationships_per_paper.csv',result['papers'])
    print('Development relationships: Recall 94.04%, Precision 85.74%, F1 89.70% — verified')

def preparation(data,out):
    folder=data/'development/preparation'
    reference={}
    for p in jsonrows(folder/'reference.jsonl'):
        for r in p['four_dimension_reference_items']+p['material_state_units']:
            key=p['reference_no'],r['id']
            if key in reference:raise ValueError('Duplicate reference identity')
            reference[key]=r['kind']
    total=Counter(reference.values());counts=Counter();seen=set()
    for r in jsonrows(folder/'decisions.jsonl'):
        key=r['reference_no'],r['id']
        if key in seen or key not in reference:raise ValueError('Invalid decision identity')
        seen.add(key)
        if r['kind']!=reference[key]:raise ValueError('Reference dimension changed')
        if r['status']=='hit':counts[r['kind']]+=1
    if seen!=set(reference):raise ValueError('Incomplete reference assessment')
    rows=[dict(dimension=k,hits=counts[k],reference_items=total[k],coverage_percent=100*counts[k]/total[k])
          for k in ['operation','parameter','order','binding','state']]
    expected={'operation':(1383,1498),'parameter':(3990,4246),'order':(943,1031),'binding':(819,909),'state':(3208,3542)}
    for r in rows:
        if (r['hits'],r['reference_items'])!=expected[r['dimension']]:raise ValueError('Preparation endpoint changed')
    save(out/'development_preparation.csv',rows)
    print('Development preparation: 11,226 reference decisions, five endpoint scores — verified')

def evolution(data,out):
    folder=data/'figures/figure2';traj=csvrows(folder/'recorded_checkpoints.csv')
    by=defaultdict(list)
    for r in traj:
        check(100*int(r['hits'])/int(r['denominator']),r['coverage_percent'],'trajectory')
        by[r['kind']].append(r)
    seq=sorted({int(r['step']) for r in traj});rank={s:n for n,s in enumerate(seq)}
    if len(seq)!=146:raise ValueError('Wrong number of recorded preparation evaluations')
    save(out/'process_evaluation_indices.csv',[dict(recorded_evaluation=rank[s],original_candidate=s) for s in seq])
    numerical=csvrows(folder/'property_trajectory_31.csv')
    for r in numerical:check(100*int(r['hits'])/int(r['denominator']),r['percent'],'numerical trajectory')
    save(out/'numerical_endpoints.csv',[r for r in numerical if r['update'] in {'0','18'}])
    paired=csvrows(folder/'paired_article_coverage.csv');pool=defaultdict(Counter)
    for r in paired:
        for key in ['before_hits','after_hits','denominator']:pool[r['kind']][key]+=int(r[key])
    for kind,vals in pool.items():
        end=max(by[kind],key=lambda r:int(r['step']))
        check(vals['after_hits'],end['hits'],'paired endpoint matches trajectory')
    save(out/'preparation_evolution_endpoints.csv',[dict(dimension=k,**v,before_percent=100*v['before_hits']/v['denominator'],after_percent=100*v['after_hits']/v['denominator']) for k,v in pool.items()])
    print('Evolution: 19 numerical evaluations, 146 preparation evaluations and paired endpoints — verified')

def prediction(data,out):
    import numpy as np
    from sklearn.linear_model import Ridge
    from polyevo_release.prediction_model import predict as annealing_predict
    def read(name):return json.loads((data/'prediction'/name).read_text(encoding='utf-8'))
    tasks={}
    def add(case,y,a,b):tasks[case]=(list(map(float,y)),list(map(float,a)),list(map(float,b)))
    first=read('annealing_two_layer_results.json')['within_paper']
    specs=csvrows(data/'tables/prediction_all13.csv')
    source_rows=csvrows(data/'prediction/annealing_34_inputs.csv')
    for r in source_rows:
        for key in ['anneal_temp_C','anneal_duration_min','published_DSC_crystallinity_pct','harmonized_net_fusion_enthalpy_J_g']:
            r[key]=float(r[key])
        r['published_baseline_pct']=float(r['published_baseline_pct']) if r['published_baseline_pct'] else None
        r['condition']=(r['anneal_temp_C'],r['anneal_duration_min'])
    refit=[]
    def fit_anneal(case,rows):
        actual=[];pa=[];pb=[]
        for condition in sorted({r['condition'] for r in rows}):
            train=[r for r in rows if r['condition']!=condition];test=[r for r in rows if r['condition']==condition]
            a=annealing_predict(train,test,'raw_pct','A',within=True)
            b=annealing_predict(train,test,'raw_pct','B',within=True)
            for r,x,z in zip(test,a,b):actual.append(r['published_DSC_crystallinity_pct']);pa.append(x);pb.append(z)
        return float(np.mean(abs(np.asarray(actual)-pa))),float(np.mean(abs(np.asarray(actual)-pb)))
    for i in range(4):
        spec=specs[i];r=next(x for x in first if x['doi']==spec['doi']);p=r['predictions']
        add(spec['case'],[x['actual_pct'] for x in p],[x['A_pct'] for x in p],[x['B_linear_pct'] for x in p])
        a,b=fit_anneal(spec['case'],[x for x in source_rows if x['doi']==spec['doi']]);refit.append(dict(case=spec['case'],A_MAE=a,B_MAE=b))
    acs=read('acs_2018_stage0_process_ablation.json')
    # Original one-variable process design standardizes each training fold.
    for case,key in [('P05','bed_temperature_valid_rows'),('P06','nozzle_temperature_rows')]:
        r=acs[key];y=np.asarray(r['target_first_heating_Xc_pct']);x=np.asarray(r['process_values_C'],dtype=float)
        a=[];b=[]
        for i in range(len(y)):
            mask=np.arange(len(y))!=i;mu=x[mask].mean();sd=x[mask].std()
            a.append(y[mask].mean());b.append(Ridge(alpha=1).fit(((x[mask]-mu)/sd)[:,None],y[mask]).predict([[(x[i]-mu)/sd]])[0])
        add(case,y,a,b)
    w=read('wang2019_stage0_within_ablation.json')
    add('P07',[r['reported_Xc_percent'] for r in w['rows']],w['scores']['A_within_paper_mean']['predictions'],w['scores']['B_temperature_and_logduration']['predictions'])
    yalk=read('annealing_yalkin2026_external_and_within.json')
    for case,section,actual,akey,bkey in [('P08','within_paper','Xc_pct','A_pred_Xc_pct','B_pred_Xc_pct'),('P09','within_paper_Tg_secondary_endpoint','Tg_C','A_pred_Tg_C','B_pred_Tg_C')]:
        p=yalk[section]['rows'];add(case,[r[actual] for r in p],[r[akey] for r in p],[r[bkey] for r in p])
    k=read('kontaxis2025_stage0_within_ablation.json')
    add('P10',[r['flexural_strength_MPa'] for r in k['rows']],k['results']['A_material_only_intercept']['predictions'],k['results']['B_both_numeric_process_fields']['predictions'])
    s=read('annealing_sensitivity_within_results.json')['paper_results']
    for case,doi in [('P11','10.3390/polym18111338'),('P12','10.3390/ma14112999')]:
        p=next(r for r in s if r['doi']==doi)['predictions'];add(case,[r['actual_pct'] for r in p],[r['A_pct'] for r in p],[r['B_linear_pct'] for r in p])
        rows=[dict(grade=r['grade'],anneal_temp_C=r['temperature_C'],anneal_duration_min=r['duration_min'],published_DSC_crystallinity_pct=r['actual_pct'],published_baseline_pct=None,condition=(r['temperature_C'],r['duration_min'])) for r in p]
        a,b=fit_anneal(case,rows);refit.append(dict(case=case,A_MAE=a,B_MAE=b))
    s=read('springer_factorial_within_ablation.json')
    add('P13',[r['xc_pct'] for r in s['rows']],s['results']['A_intercept']['predictions'],s['results']['B_additive_five_numeric_process_fields']['predictions'])
    rows=[];preds=[]
    for spec in specs:
        case=spec['case'];y,a,b=tasks[case]
        ma=sum(abs(i-j) for i,j in zip(y,a))/len(y);mb=sum(abs(i-j) for i,j in zip(y,b))/len(y)
        check(ma,spec['A_MAE'],case+' baseline');check(mb,spec['B_MAE'],case+' preparation')
        rows.append(dict(case=case,A_MAE=ma,B_MAE=mb,doi=spec['doi'],unit=spec['unit']))
        preds.extend(dict(case=case,row=i+1,actual=v,A_prediction=a[i],preparation_prediction=b[i]) for i,v in enumerate(y))
    for r in refit:
        spec=next(s for s in specs if s['case']==r['case'])
        check(r['A_MAE'],spec['A_MAE'],r['case']+' refitted baseline')
        check(r['B_MAE'],spec['B_MAE'],r['case']+' refitted preparation')
    save(out/'prediction_refitted.csv',refit)
    save(out/'prediction_all13_recomputed.csv',rows);save(out/'prediction_rows.csv',preds)
    print('Prediction: all 13 task MAEs — verified')

def retention(data,out):
    from polyevo_release.retention import propose
    rows=list(jsonrows(data/'examples/retention_records.jsonl'))
    aliases,changes=propose(rows)
    expected={r['prediction_id']:r['representative_prediction_id'] for r in csvrows(data/'examples/retention_expected.csv')}
    if aliases!=expected:raise ValueError('Archived duplicate-handling example did not replay exactly')
    save(out/'retention_replay.csv',[dict(prediction_id=k,representative_prediction_id=v) for k,v in aliases.items()])
    print('Retention example: 16 archived duplicate occurrences — replayed')

def baselines(data,out):
    counts=csvrows(data/'baselines/property_baseline_counts.csv');rows=[]
    for r in counts:
        tp,gold,fp,u=(int(r[k]) for k in ['tp','gold','fp','unresolved_in_scope'])
        recall=tp/gold;precision=tp/(tp+fp+u);f1=2*recall*precision/(recall+precision)
        for key,value in [('recall_confirmed',recall),('precision_confirmed',precision),('f1_confirmed',f1)]:check(value,r[key],r['method']+' '+key)
        rows.append(dict(method=r['method'],Recall=100*recall,Precision=100*precision,F1=100*f1))
    save(out/'property_baselines.csv',rows)
    refs={(r['reference_no'],r['id']):r['kind'] for r in jsonrows(data/'baselines/preparation_reference.jsonl')}
    expected={'KnowMat2':{'operation':97,'parameter':164,'order':42,'binding':38},'PromptDataExtraction':{'operation':114,'parameter':231,'order':26,'binding':34}}
    totals=Counter(refs.values());rows=[]
    for method,path in [('KnowMat2','tables/knowmat2_preparation_decisions_20261104.csv'),('PromptDataExtraction','baselines/promptdata_preparation_decisions.csv')]:
        records=csvrows(data/path);seen=set();hits=Counter()
        for r in records:
            key=r['reference_no'],r.get('reference_id',r.get('id'))
            if key in seen or key not in refs:raise ValueError('Invalid baseline reference identity')
            seen.add(key)
            if r['kind']!=refs[key]:raise ValueError('Baseline reference dimension changed')
            if r['verdict']=='hit':hits[r['kind']]+=1
        if seen!=set(refs):raise ValueError('Incomplete baseline decisions')
        if dict(hits)!=expected[method]:raise ValueError('Baseline preparation endpoint changed')
        rows.extend(dict(method=method,dimension=k,hits=hits[k],reference_items=totals[k],coverage_percent=100*hits[k]/totals[k]) for k in ['operation','parameter','order','binding'])
    save(out/'preparation_baselines.csv',rows)
    print('Baseline scores: four property configurations and two preparation configurations — verified')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--task',choices=['all','relationships','preparation','evolution','prediction','retention','baselines'],default='all');args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    for name,fn in [('relationships',relationships),('preparation',preparation),('evolution',evolution),('prediction',prediction),('retention',retention),('baselines',baselines)]:
        if args.task in {'all',name}:fn(args.data.resolve(),args.output.resolve())

if __name__=='__main__':main()
