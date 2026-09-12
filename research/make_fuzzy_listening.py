#!/usr/bin/env python3
"""Four-way blind packs: exact fuzzy ablations OR original derived comparison.

Only distribute listener/. analyst/ has the key. Winner CSVs are consumed by
score_blind_votes.py with explicit listener IDs. There are no generated ratings.
"""
from __future__ import annotations
import argparse,csv,hashlib,html,itertools,json,random,tempfile
from collections import defaultdict
from pathlib import Path
import soundfile as sf
import eval_fuzzy_corpus as e
from make_blind_multires_pack import level_match,load_trial


def read_evaluation(root: Path) -> tuple[dict,list[dict]]:
    summary=json.loads((root/'summary.json').read_text())
    if summary.get('schema')!=e.SCHEMA or summary.get('mos_transfer') is not False or summary.get('complete',True) is not True:
        raise ValueError('not a complete fuzzy evaluation')
    if e.fingerprint(root/'metrics.csv')!=summary['metrics_sha256']:raise ValueError('metrics hash mismatch')
    with (root/'metrics.csv').open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
    for r in rows:
        for k in ('sample_rate','frames','channels','duration_error_frames','peak_channel','samples_above_unity'):r[k]=int(r[k])
        for k in ('pitch_semitones','control_ratio','measured_ratio','env','onset','rms','peak','peak_time_seconds'):r[k]=float(r[k])
    e.validate(rows,summary['cells'],summary['formants'])
    if len(rows)!=summary['measurements']:raise ValueError('measurement count mismatch')
    return summary,rows


def player(trials: list[dict], pack_id: str) -> str:
    sections=[]
    for trial in trials:
        t=trial['trial'];audio=f'audio/T{t:03d}/'
        controls=''.join(f'<h3>{label}</h3><audio controls preload="none" src="{audio}{label}.wav"></audio>' for label in 'ABCD')
        scores=''.join(f'<label>{label} <select data-trial="{t}" data-criterion="{c}"><option value=""></option>'+
            ''.join(f'<option>{v}</option>' for v in 'ABCD')+'</select></label> ' for c,label in
            [('overall','総合'),('attack','立ち上がり'),('tone','音色・ノイズの自然さ')])
        sections.append(f'<section><h2>T{t:03d} · {html.escape(trial["category"])} · {trial["semitones"]:+.2f} st</h2>'+
            f'<p>原音参照（音高未変更、再生用レベル調整済み）</p><audio controls preload="none" src="{audio}reference.wav"></audio>'+
            controls+'<p>各項目で最も良い候補を選択。判断できない場合は空欄。</p>'+scores+'</section>')
    return '''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>匿名音声比較</title><style>body{font:16px system-ui;max-width:900px;margin:2em auto;padding:0 1em;line-height:1.6}
section{border-top:1px solid #999;padding:1em 0;margin:1em 0}audio{width:min(100%,500px)}select,button{padding:.5em}h3{margin-bottom:.2em}</style>
<h1>匿名音声比較</h1><p>再生音量は固定してください。原音は音色の参照用で、音高を揃えた正解音ではありません。
未回答は勝敗に含めません。自動保存しないため、終了前にCSVを書き出してください。</p>
<button id="export">投票CSVを書き出す</button><span id="status" role="status"></span>
'''+''.join(sections)+'''<script>
'use strict';
const packId='''+json.dumps(pack_id)+''';
const trials='''+json.dumps([t['trial'] for t in trials])+''';
const criteria=['overall','attack','tone'];
const csvCell=v=>'"'+String(v).replaceAll('"','""')+'"';
document.addEventListener('play',e=>document.querySelectorAll('audio').forEach(a=>{if(a!==e.target)a.pause();}),true);
document.getElementById('export').onclick=()=>{
 const rows=[['trial','pack_id',...criteria]];
 for(const trial of trials)rows.push([trial,packId,...criteria.map(c=>document.querySelector(`[data-trial="${trial}"][data-criterion="${c}"]`).value)]);
 const url=URL.createObjectURL(new Blob([rows.map(r=>r.map(csvCell).join(',')).join('\\r\\n')+'\\r\\n'],{type:'text/csv;charset=utf-8'}));
 const a=document.createElement('a');a.href=url;a.download='votes.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 document.getElementById('status').textContent=' 書き出しました。CSVを保存してください。';
};
</script></html>'''


def make_pack(evaluation: Path, refs: Path, output: Path, kind: str, per_category: int,
              formant: str='harmonic', seed: int=20260913) -> dict:
    if kind not in ('candidate','derived') or per_category<1:raise ValueError('invalid pack selection')
    summary,rows=read_evaluation(evaluation)
    if formant not in summary['formants']:raise ValueError('formant policy not evaluated')
    profiles=('transient','multires','fuzzy-noise','fuzzy') if kind=='candidate' else ('general','transient','multires',e.BASELINE)
    family='exact' if kind=='candidate' else 'derived'
    cells=[c for c in summary['cells'] if c['family']==family and c['scope']=='target']
    groups=defaultdict(set)
    for c in cells:groups[c['review_category']].add(c['stem'])
    if not groups or any(len(stems)<per_category for stems in groups.values()):raise ValueError('insufficient sources per review category')
    rng=random.Random(seed);selected=[]
    for category,stems in sorted(groups.items()):selected+=rng.sample(sorted(stems),per_category)
    cells=[c for c in cells if c['stem'] in selected];rng.shuffle(cells)
    identity=dict(evaluation_sha256=e.fingerprint(evaluation/'summary.json'),kind=kind,formant=formant,seed=seed,per_category=per_category)
    pack_id=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    indexed={(r['condition_id'],r['profile'],r['formant']):r for r in rows}
    output=output.resolve()
    if output.exists():raise ValueError('output already exists')
    output.parent.mkdir(parents=True,exist_ok=True)
    keys=[];public=[];permutations=[]
    with tempfile.TemporaryDirectory(prefix='.blind-fuzzy-',dir=output.parent) as tmp:
        stage=Path(tmp)/'pack';listener=stage/'listener';analyst=stage/'analyst'
        listener.mkdir(parents=True);analyst.mkdir()
        for i,c in enumerate(cells):
            if not permutations:permutations=list(itertools.permutations(profiles));rng.shuffle(permutations)
            mapping=dict(zip('ABCD',permutations.pop()))
            paired={p:indexed[(c['condition_id'],p,'not_applicable' if p==e.BASELINE else formant)] for p in profiles}
            reference=e.inside(refs,c['reference_name']);paths={p:e.inside(evaluation,r['render_path']) for p,r in paired.items()}
            if e.fingerprint(reference)!=c['reference_sha256'] or any(e.fingerprint(paths[p])!=r['render_sha256'] for p,r in paired.items()):
                raise ValueError('audio hash mismatch')
            ref,audio,rate=load_trial(reference,paths)
            if rate!=c['sample_rate'] or ref.shape!=(c['frames'],c['channels']):raise ValueError('trial metadata mismatch')
            ref,audio=level_match(ref,audio);folder=listener/'audio'/f'T{i+1:03d}';folder.mkdir(parents=True)
            sf.write(folder/'reference.wav',ref,rate,subtype='PCM_16')
            for label,p in mapping.items():sf.write(folder/(label+'.wav'),audio[p],rate,subtype='PCM_16')
            item=dict(trial=i+1,category=c['review_category'],semitones=c['pitch_semitones'])
            public.append(item);keys.append(dict(trial=i+1,pack_id=pack_id,category=c['review_category'],formant=formant,
                semitones=c['pitch_semitones'],condition_id=c['condition_id'],stem=c['stem'],**mapping))
        with (analyst/'answer_key.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(keys[0]));w.writeheader();w.writerows(keys)
        (listener/'index.html').write_text(player(public,pack_id),encoding='utf-8')
        (listener/'manifest.json').write_text(json.dumps(dict(pack_id=pack_id,trials=public,
            audio_policy='capped +/-6dB RMS match, shared 0.95 headroom, PCM16; unshifted source reference'),indent=2)+'\n')
        with (listener/'votes.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=['trial','pack_id','overall','attack','tone']);w.writeheader()
            for t in public:w.writerow(dict(trial=t['trial'],pack_id=pack_id))
        info=dict(pack_id=pack_id,**identity,trials=len(public),source_count=len(selected),profiles=list(profiles),
                  listening_status='not_listened',listener_sha256={p.relative_to(listener).as_posix():e.fingerprint(p) for p in sorted(listener.rglob('*')) if p.is_file()})
        (analyst/'provenance.json').write_text(json.dumps(info,indent=2)+'\n')
        stage.rename(output)
    return info

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('evaluation','ref-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--kind',choices=('candidate','derived'),required=True);p.add_argument('--per-category',type=int,default=1)
    p.add_argument('--formant',default='harmonic');p.add_argument('--seed',type=int,default=20260913)
    a=p.parse_args();r=make_pack(a.evaluation,a.ref_dir,a.output,a.kind,a.per_category,a.formant,a.seed)
    print(json.dumps({k:v for k,v in r.items() if k!='listener_sha256'},indent=2))
