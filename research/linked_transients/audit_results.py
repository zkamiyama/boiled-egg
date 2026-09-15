#!/usr/bin/env python3
"""Verify manifest grids, then retain paired improvements AND regressions.
No winning-mode selector, perceptual percentage or native-vendor comparison.
"""
import argparse, csv, hashlib, json
from pathlib import Path
import numpy as np

MODES=('locked','heap','independent_legacy','independent_linked','shared_long','shared_linked','localized_shared')
PILOT={'Ardour_2','Female_4','Male_6','Rock_4','Triangle_02'}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def verify(root):
    report=json.loads((root/'summary.json').read_text())
    if sha(root/'measurements.csv')!=report['measurements_sha256']:raise ValueError('measurement hash')
    manifest=json.loads((root.parent/(root.name+'-journal')/'manifest.json').read_text())
    if hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()!=report['identity']:raise ValueError('manifest identity')
    with (root/'measurements.csv').open(newline='') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames or []
        if len(fields)!=len(set(fields)):raise ValueError('duplicate column')
        rows=list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in rows):raise ValueError('ragged CSV')
    if report['suite']=='detector':
        expected={(j[0],j[1],j[2],j[3],j[4],m) for j in manifest['jobs'] for m in ('legacy40','global6','linked6')}
        keys=[(int(r['rate']),int(r['spacing_ms']),float(r['level']),r['same_channel']=='True',r['mixed']=='True',r['mode']) for r in rows]
    else:
        expected={(j[1],j[2],j[3],j[4],m) for j in manifest['jobs'] for m in MODES}
        keys=[(r['source'],int(r['rate']),float(r['ratio']),int(r['seed']),r['mode']) for r in rows]
    if len(keys)!=len(set(keys)) or set(keys)!=expected or len(rows)!=report['rows']:raise ValueError('incomplete/duplicate grid')
    # Every CSV value is also checked against its hashed per-case journal record.
    journal=root.parent/(root.name+'-journal');records=[]
    for i in range(len(manifest['jobs'])):
        blob=json.loads((journal/f'{i:04}.json').read_text())
        if blob['identity']!=report['identity'] or blob['index']!=i or hashlib.sha256(json.dumps(blob['rows'],sort_keys=True).encode()).hexdigest()!=blob['sha256']:
            raise ValueError('journal payload')
        records.extend(blob['rows'])
    for row,record in zip(rows,records):
        if any(row[k]!=('' if k not in record else str(record[k])) for k in fields):raise ValueError('CSV/journal disagreement')
        if any(not np.isfinite(v) for v in record.values() if isinstance(v,float)):raise ValueError('nonfinite value')
    return records,report

def paired(rows,candidate,control,metric,higher=False):
    key=lambda r:(r['source'],r['rate'],r['ratio'],r['seed'])
    a={key(r):r for r in rows if r['mode']==candidate and metric in r}
    b={key(r):r for r in rows if r['mode']==control and metric in r}
    if not a or set(a)!=set(b):raise ValueError('unpaired metrics')
    keys=sorted(a);diff=np.array([a[k][metric]-b[k][metric] for k in keys])
    sources=sorted({k[0] for k in keys});cluster=np.array([np.mean([d for k,d in zip(keys,diff) if k[0]==s]) for s in sources])
    rng=np.random.default_rng(26091591);boot=cluster[rng.integers(0,len(cluster),(4000,len(cluster)))].mean(axis=1)
    benefit=diff if higher else -diff;worst=int(np.argmin(benefit))
    return dict(candidate=candidate,control=control,metric=metric,conditions=len(keys),sources=len(sources),
        candidate_mean=float(np.mean([a[k][metric] for k in keys])),control_mean=float(np.mean([b[k][metric] for k in keys])),
        delta=float(diff.mean()),ci95=list(map(float,np.quantile(boot,[.025,.975]))),
        wins=int((benefit>1e-9).sum()),losses=int((benefit < -1e-9).sum()),ties=int((abs(benefit)<=1e-9).sum()),
        worst=dict(source=keys[worst][0],ratio=keys[worst][2],delta=float(diff[worst])))

def run(root,output):
    if output.exists():raise ValueError('new output required')
    suites={};reports={}
    for suite in ('detector','synthetic','mixtures','corpus'):suites[suite],reports[suite]=verify(root/suite)
    comparisons=[]
    for cohort,rows in [('all20',suites['corpus']),('other15',[r for r in suites['corpus'] if r['source'] not in PILOT])]:
        for candidate,control in [('independent_linked','independent_legacy'),('shared_linked','independent_linked'),('localized_shared','independent_legacy'),('localized_shared','heap'),('localized_shared','locked')]:
            for metric in ('rms_shape_db','onset_corr','global_psd_shape_db','local_spectral_2048_db'):
                comparisons.append(dict(cohort=cohort,**paired(rows,candidate,control,metric,metric=='onset_corr')))
    detector=[]
    for same in (False,True):
        for mixed in (False,True):
            for mode in ('legacy40','global6','linked6'):
                group=[r for r in suites['detector'] if r['same_channel']==same and r['mixed']==mixed and r['mode']==mode]
                tp=sum(r['tp'] for r in group);fp=sum(r['fp'] for r in group);fn=sum(r['fn'] for r in group)
                detector.append(dict(same_channel=same,mixed=mixed,mode=mode,conditions=len(group),tp=tp,fp=fp,fn=fn,recall=tp/(tp+fn),precision=tp/(tp+fp) if tp+fp else 0.))
    means=[]
    for suite in ('synthetic','mixtures','corpus'):
        rows=[r for r in suites[suite] if r['ratio']!=1]
        for name in sorted({r['source'] for r in rows}) if suite=='synthetic' else ('all',):
            for mode in MODES:
                group=[r for r in rows if r['mode']==mode and (name=='all' or r['source']==name)]
                fields=('rms_shape_db','onset_corr','global_psd_shape_db','local_spectral_2048_db','width_error_ms','centroid_error_ms','energy_error_db','outside_support_fraction','partial_error_db')
                means.append(dict(suite=suite,source=name,mode=mode,conditions=len(group),max_peak=max(r['peak'] for r in group),
                    **{m:float(np.mean([r[m] for r in group])) for m in fields if m in group[0]}))
    result=dict(primary_outputs=sum(reports[s]['generated_outputs'] for s in reports),detector_comparisons=len(suites['detector']),
        means=means,detector=detector,paired=comparisons,inputs={s:sha(root/s/'summary.json') for s in suites},
        caveat='Source-cluster4000 draws, seed26091591; descriptive, no multiplicity correction. Reused real corpus. No audio listening or native baseline.')
    output.mkdir();(output/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    for name,rows in [('means',means),('detector',detector),('paired',comparisons)]:
        with (output/(name+'.csv')).open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=sorted(set().union(*(r.keys() for r in rows))));writer.writeheader();writer.writerows(rows)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--results',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=run(a.results,a.output);print(r['primary_outputs'],'outputs audited;',r['detector_comparisons'],'detector comparisons')
