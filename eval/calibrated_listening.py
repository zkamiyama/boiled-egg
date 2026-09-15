#!/usr/bin/env python3
"""Roadmap B: operation evidence -> complete raw panel -> anonymous listening.

Reuses A-stage receipt validation and the existing multi-choice player pattern.
No directory scanning of unverified renders, nearest-ratio matching, hidden
fallback, per-system output correction or fabricated listener ratings.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import html
import json
import math
from pathlib import Path
import random
import tempfile

import numpy as np
import soundfile as sf
import comparison_contract as c
import candidate_evidence as e


def run_panel(calibration: Path, sources: list[Path], operations: list[tuple[float,float]],
              candidates: list[e.Candidate], root: Path) -> dict:
    plan,coverage=e.verify_calibration(calibration)
    e.panel_validate(candidates)
    if len(candidates)<2:raise ValueError('comparison requires at least two explicitly selected systems')
    sources=[p.resolve(strict=True) for p in sources]
    if not sources or len(sources)!=len(set(sources)):raise ValueError('unique nonempty source list required')
    requests=[c.Request.from_semitones(t,p) for t,p in operations]
    if not requests or len({e.digest(asdict(r)) for r in requests})!=len(requests):raise ValueError('unique operation list required')
    observed={p.name:p.probe() for p in candidates}
    probes={}
    for name,current in observed.items():
        recorded=plan['probes'].get(name)
        # ldd includes ASLR addresses: compare execution identity, not log text.
        if recorded is None or any(current[k]!=recorded[k] for k in ('config','files','wrappers','software')):
            raise ValueError('candidate execution identity differs from calibration')
        probes[name]=recorded
    metadata={str(p):c.inspect_audio(p) for p in sources}
    jobs=[]
    for index,source in enumerate(sources):
        for op,request in enumerate(requests):
            for p in candidates:
                m=metadata[str(source)]
                key=e.require_eligible(plan,coverage,probes[p.name],m['sample_rate'],m['channels'],request)
                jobs.append(dict(source=str(source),candidate=p.name,request=asdict(request),
                    case=f'cases/{index:04}-{op:02}-{p.name}',trial=f'{index:04}-{op:02}',calibration_key=key))
    # All eligibility checks happen before rendering; no quietly reduced panel.
    root.mkdir(parents=True,exist_ok=False)
    frozen=dict(schema='boiled-egg.eligible-panel-plan.v1',probes=probes,observed_probes=observed,sources=metadata,jobs=jobs,
                runner_sha256=c.fingerprint(Path(__file__)),
                calibration_summary_sha256=c.fingerprint(calibration/'summary.json'),
                purpose='operation-calibrated exploratory listening; alignment and formant fidelity not qualified')
    c.json_write(root/'plan.json',frozen)
    by_name={p.name:p for p in candidates};rows=[]
    for i,job in enumerate(jobs):
        receipt=e.render(by_name[job['candidate']],probes[job['candidate']],Path(job['source']),
                         c.Request(**job['request']),root/job['case'])
        rows.append(dict(**job,status=receipt['status'],receipt_sha256=c.fingerprint(root/job['case']/'receipt.json')))
        if (i+1)%20==0:print('natural panel',i+1,'/',len(jobs),flush=True)
    unchanged=all(c.fingerprint(Path(p))==m['sha256'] for p,m in metadata.items()) and all(e.stable(p) for p in probes.values())
    report=dict(schema='boiled-egg.eligible-panel.v1',passed=unchanged and all(r['status']=='passed' for r in rows),
                plan_sha256=c.fingerprint(root/'plan.json'),rows=rows,expected_cells=len(jobs),identities_stable=unchanged,
                listening_status='not_listened',quality_selection=None)
    c.json_write(root/'summary.json',report)
    return report


def verify_panel(root: Path, calibration: Path) -> tuple[dict,list[dict]]:
    root=root.resolve(strict=True)
    report=json.loads((root/'summary.json').read_text());plan=json.loads((root/'plan.json').read_text())
    if (report.get('schema')!='boiled-egg.eligible-panel.v1' or not report.get('passed') or not report.get('identities_stable')
            or c.fingerprint(root/'plan.json')!=report['plan_sha256']
            or c.fingerprint(calibration/'summary.json')!=plan['calibration_summary_sha256']):
        raise ValueError('failed or changed panel/evidence; no listening pack')
    cp,coverage=e.verify_calibration(calibration)
    expected={j['case']:j for j in plan['jobs']}
    rows=report['rows']
    if len(expected)!=len(plan['jobs']) or len(rows)!=len(expected) or len(rows)!=report['expected_cells'] or set(r['case'] for r in rows)!=set(expected):
        raise ValueError('incomplete/duplicate panel')
    receipts=[]
    for row in rows:
        job=expected[row['case']]
        if any(row[k]!=v for k,v in job.items()) or row['status']!='passed':raise ValueError('panel identity changed')
        case=e.inside(root,row['case'])
        if c.fingerprint(case/'receipt.json')!=row['receipt_sha256']:raise ValueError('changed panel receipt')
        receipt=c.verify_case(case);name=row['candidate'];source=plan['sources'][row['source']]
        key=e.require_eligible(cp,coverage,plan['probes'][name],source['sample_rate'],source['channels'],c.Request(**row['request']))
        if (key!=row['calibration_key'] or receipt['source_metadata']!=source or receipt['request']!=row['request']
                or receipt['candidate_identity']!=e.digest(plan['probes'][name]) or receipt['engine']!=name):
            raise ValueError('render does not match calibrated plan')
        receipts.append(receipt)
    for source,metadata in plan['sources'].items():
        if c.inspect_audio(Path(source))!=metadata:raise ValueError('original orientation audio changed')
    return plan,receipts


def html_page(trials: list[dict], pack_id: str) -> str:
    cards=[]
    for trial in trials:
        choices=[]
        for choice in trial['choices']:
            labels=''.join(f'<label>{text}<select data-trial="{trial["trial"]}" data-choice="{choice["label"]}" data-dimension="{dimension}"><option value="">未回答</option>'+''.join(f'<option value="{n}">{n}</option>' for n in range(1,6))+'</select></label>'
                for dimension,text in [('naturalness','自然さ'),('attack','立ち上がり'),('sustain','持続音の明瞭さ')])
            choices.append(f'<section><h3>{choice["label"]}</h3><audio controls preload="none" src="{choice["file"]}"></audio>{labels}</section>')
        request=trial['request'];pitch=12*math.log2(request['pitch_ratio'])
        cards.append(f'<article><h2>{trial["trial"]} — 長さ{request["duration_ratio"]:g}倍／音程{pitch:+g}半音</h2><p>原音（方向確認用。変換後の正解ではありません）</p><audio controls preload="none" src="{trial["original"]}"></audio><div>{"".join(choices)}</div></article>')
    # All file names and labels are generated internally, not source metadata.
    return '''<!doctype html><html lang="ja"><meta charset="utf-8"><title>匿名音声比較</title>
<style>body{font:16px system-ui,sans-serif;max-width:1150px;margin:2em auto;padding:1em}article{border-top:1px solid;padding:1em 0}article div{display:flex;gap:1em;flex-wrap:wrap}section{flex:1;min-width:230px}label{display:block;margin:.5em 0}audio{max-width:100%}button{padding:1em}</style>
<h1>変換音の匿名比較</h1><p>校正済みの操作条件に限定した探索的な試聴です。正式な品質認定ではありません。1＝悪い、5＝良い。未回答は採点されません。原音と候補全体に同じ減衰のみを適用し、個別の音量差は残しています。音量を低くしてから再生してください。</p>
''' + ''.join(cards) + '''<button id="export">明示的に回答した評価だけ保存</button><script>
const packId='''+json.dumps(pack_id)+''';
document.getElementById('export').onclick=()=>{const ratings=[];for(const e of document.querySelectorAll('select'))if(e.value!=='')ratings.push({trial:e.dataset.trial,choice:e.dataset.choice,dimension:e.dataset.dimension,rating:Number(e.value)});const blob=new Blob([JSON.stringify({pack_id:packId,ratings},null,2)],{type:'application/json'});const u=URL.createObjectURL(blob),a=document.createElement('a');a.href=u;a.download='ratings.json';a.click();URL.revokeObjectURL(u);};
</script></html>'''


def make_pack(root: Path, calibration: Path, output: Path, seed: int=260915) -> dict:
    if output.exists():raise ValueError('new pack directory required')
    plan,receipts=verify_panel(root,calibration)
    if type(seed) is not int:raise ValueError('integer randomization seed required')
    source_rows=json.loads((root/'summary.json').read_text())['rows']
    groups={}
    for row,receipt in zip(source_rows,receipts):groups.setdefault(row['trial'],[]).append((row,receipt))
    rng=random.Random(seed);order=list(groups);rng.shuffle(order)
    pack_id=e.digest(dict(plan=plan,receipts=[r['raw_output_sha256'] for r in receipts],seed=seed))
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.listening-pack-',dir=output.parent) as temporary:
        stage=Path(temporary)/'pack';public=stage/'listener';private=stage/'organizer';audio=public/'audio'
        audio.mkdir(parents=True);private.mkdir();trials=[];key=[]
        for i,group in enumerate(order,1):
            entries=list(groups[group]);rng.shuffle(entries);trial=f'T{i:03d}'
            original=Path(entries[0][0]['source']);sm=plan['sources'][str(original)]
            max_peak=max([sm['peak'],*[r['output']['peak'] for _,r in entries]])
            gain=min(1.,.95/max(max_peak,1e-30))
            def present(path: Path, name: str) -> dict:
                x,rate=sf.read(path,dtype='float64',always_2d=True);dest=audio/name
                sf.write(dest,x*gain,rate,subtype='FLOAT')
                actual,_=sf.read(dest,dtype='float32',always_2d=True)
                if not np.array_equal(actual,(x*gain).astype('float32')):raise ValueError('presentation transform mismatch')
                return dict(file='audio/'+name,sha256=c.fingerprint(dest))
            original_record=present(original,trial+'_original.wav')
            choices=[]
            for j,(row,receipt) in enumerate(entries):
                label=chr(65+j);item=present(root/row['case']/'output.wav',trial+'_'+label+'.wav')
                choices.append(dict(label=label,**item))
                key.append(dict(trial=trial,choice=label,candidate=row['candidate'],source=row['source'],
                    request=row['request'],raw_sha256=receipt['raw_output_sha256'],presentation_sha256=item['sha256'],
                    common_gain=gain,common_gain_db=20*math.log10(gain),calibration_key=row['calibration_key']))
            trials.append(dict(trial=trial,request=entries[0][0]['request'],original=original_record['file'],
                               original_sha256=original_record['sha256'],choices=choices))
        c.json_write(public/'trials.json',dict(pack_id=pack_id,trials=trials))
        (public/'index.html').write_text(html_page(trials,pack_id),encoding='utf-8')
        c.json_write(private/'key.json',dict(pack_id=pack_id,seed=seed,choices=key))
        c.json_write(private/'evidence.json',dict(plan=plan,receipts=receipts,calibration_summary_sha256=c.fingerprint(calibration/'summary.json')))
        report=dict(pack_id=pack_id,trials=len(trials),choices=len(key),listening_status='not_listened',
                    ratings_received=0,quality_selection=None,alignment_verified=False,formant='off',
                    presentation='one common peak-safe attenuation per trial; no per-candidate normalization or alignment')
        c.json_write(private/'summary.json',report)
        verify_panel(root,calibration)  # Recheck immutable raw evidence after presentation creation.
        stage.rename(output)
    return report


def validate_answers(pack: Path, answers: dict) -> list[dict]:
    public=json.loads((pack/'listener/trials.json').read_text())
    if set(answers)!={'pack_id','ratings'} or answers['pack_id']!=public['pack_id'] or not isinstance(answers['ratings'],list):
        raise ValueError('wrong pack or answer schema')
    allowed={(t['trial'],c['label'],dimension) for t in public['trials'] for c in t['choices']
             for dimension in ('naturalness','attack','sustain')};seen=set()
    for row in answers['ratings']:
        if set(row)!={'trial','choice','dimension','rating'}:raise ValueError('invalid rating schema')
        key=(row['trial'],row['choice'],row['dimension'])
        if key not in allowed or key in seen or type(row['rating']) not in (float,int) or not math.isfinite(row['rating']) or not 1<=row['rating']<=5:
            raise ValueError('unknown/duplicate/nonfinite/out-of-range rating')
        seen.add(key)
    return answers['ratings']  # Empty means zero actual responses, never a default score.


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    cal=sub.add_parser('calibrate');cal.add_argument('--panel',type=Path,required=True);cal.add_argument('--output',type=Path,required=True)
    run=sub.add_parser('render');run.add_argument('--panel',type=Path,required=True);run.add_argument('--calibration',type=Path,required=True)
    run.add_argument('--requests',type=Path,required=True,help='JSON object: sources list and operations [[duration,semitones], ...]')
    run.add_argument('--output',type=Path,required=True)
    pack=sub.add_parser('pack');pack.add_argument('--run',type=Path,required=True);pack.add_argument('--calibration',type=Path,required=True)
    pack.add_argument('--output',type=Path,required=True);pack.add_argument('--seed',type=int,default=260915)
    a=p.parse_args()
    if a.action=='pack':report=make_pack(a.run,a.calibration,a.output,a.seed)
    else:
        panel=[e.Candidate(**x) for x in json.loads(a.panel.read_text())]
        if a.action=='calibrate':report=e.calibrate(panel,a.output)
        else:
            req=json.loads(a.requests.read_text());report=run_panel(a.calibration,[Path(x) for x in req['sources']],req['operations'],panel,a.output)
    print(json.dumps(report if a.action=='pack' else {k:v for k,v in report.items() if k not in ('rows',)},indent=2))
    return 0 if report.get('passed',True) else 1

if __name__=='__main__':raise SystemExit(main())
