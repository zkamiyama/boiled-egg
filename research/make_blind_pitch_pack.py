#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, html, random
from collections import defaultdict
from pathlib import Path
import numpy as np
import soundfile as sf

SYSTEM_FILES={
    'elastique':'elastique.wav',
    'off':'boiled_off.wav',
    'harmonic':'boiled_harmonic.wav',
    'monophonic':'boiled_monophonic.wav',
}

def read_conditions(metrics:Path):
    rows=list(csv.DictReader(metrics.open()))
    return [r for r in rows if r['system']=='elastique']

def allocate_counts(groups,total):
    keys=sorted(groups)
    base=total//len(keys); rem=total%len(keys)
    return {k:min(len(groups[k]),base+(i<rem)) for i,k in enumerate(keys)}

def spaced_select(rows,count):
    rows=sorted(rows,key=lambda r:float(r['semitones']))
    if count>=len(rows):return rows
    idx=np.linspace(0,len(rows)-1,count)
    chosen=[];used=set()
    for x in idx:
        i=int(round(float(x)))
        while i in used and i+1<len(rows):i+=1
        while i in used and i-1>=0:i-=1
        used.add(i);chosen.append(rows[i])
    return chosen

def load_audio(path):
    y,sr=sf.read(path,always_2d=True,dtype='float32')
    return y.astype(np.float64),sr

def rms(y):return float(np.sqrt(np.mean(y*y)+1e-30))
def db_to_gain(db):return 10.0**(db/20.0)

def level_match(reference,systems,max_gain_db=6.0,headroom=0.95):
    rr=rms(reference); out={}
    cap=db_to_gain(max_gain_db); floor=1.0/cap
    for name,y in systems.items():
        g=np.clip(rr/max(rms(y),1e-30),floor,cap)
        out[name]=y*g
    maxpeak=max([float(np.max(np.abs(reference)))] + [float(np.max(np.abs(y))) for y in out.values()])
    common=min(1.0,headroom/max(maxpeak,1e-30))
    return reference*common,{k:v*common for k,v in out.items()}

def write_html(path,manifest_rows,labels):
    trials=[]
    for r in manifest_rows:
        t=r['trial']
        opts=''.join(f'<div><b>{lab}</b> <audio controls preload="none" src="{html.escape(r[lab])}"></audio> <label><input type="radio" name="pick-{t}" value="{lab}"> best</label></div>' for lab in labels)
        trials.append(f'<section><h3>Trial {t} — {html.escape(r["category"])} — {float(r["semitones"]):+.2f} st</h3><div><b>Reference</b> <audio controls preload="none" src="{html.escape(r["reference"])}"></audio></div>{opts}</section>')
    doc='''<!doctype html><meta charset="utf-8"><title>boiled egg blind pitch test</title>
<style>body{font-family:sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem}section{border-top:1px solid #bbb;padding:1rem 0}audio{width:420px;vertical-align:middle;margin:.25rem 1rem}.toolbar{position:sticky;top:0;background:white;padding:.5rem 0}</style>
<h1>boiled egg blind pitch test</h1><p>Compare each anonymous render against the reference. Loudness is RMS-matched per trial; system identities are in <code>answer_key.csv</code>.</p>
<div class="toolbar"><button onclick="save()">Export choices.csv</button></div>'''+''.join(trials)+'''<script>
function save(){let lines=['trial,pick']; document.querySelectorAll('section').forEach((s,i)=>{let x=s.querySelector('input:checked');lines.push((i+1)+','+(x?x.value:''));});let b=new Blob([lines.join('\\n')+'\\n'],{type:'text/csv'});let a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='choices.csv';a.click();}
</script>'''
    path.write_text(doc,encoding='utf-8')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--metrics',type=Path,required=True)
    ap.add_argument('--renders',type=Path,required=True)
    ap.add_argument('--ref-dir',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--trials',type=int,default=24)
    ap.add_argument('--seed',type=int,default=20260830)
    ap.add_argument('--systems',default='elastique,off,harmonic,monophonic')
    args=ap.parse_args()
    systems=tuple(x.strip() for x in args.systems.split(',') if x.strip())
    for s in systems:
        if s not in SYSTEM_FILES:raise SystemExit(f'unknown system {s}')
    labels=tuple(chr(ord('A')+i) for i in range(len(systems)))
    groups=defaultdict(list)
    for r in read_conditions(args.metrics):groups[r['category']].append(r)
    counts=allocate_counts(groups,args.trials)
    selected=[]
    for cat in sorted(groups):selected.extend(spaced_select(groups[cat],counts[cat]))
    selected.sort(key=lambda r:(r['category'],float(r['semitones'])))
    args.output.mkdir(parents=True,exist_ok=True)
    rng=random.Random(args.seed); manifest=[]; key=[]
    for ti,r in enumerate(selected,1):
        stem=r['stem']; percent=r['percent']; source_dir=args.renders/stem/f'{percent}_per'
        if not source_dir.exists():
            folders=list((args.renders/stem).glob('*_per'))
            source_dir=min(folders,key=lambda p:abs(float(p.name[:-4])-float(percent)))
        ref,ref_sr=load_audio(args.ref_dir/f'{stem}.wav')
        aud={}
        for s in systems:
            aud[s],sr=load_audio(source_dir/SYSTEM_FILES[s])
            if sr!=ref_sr or len(aud[s])!=len(ref):raise SystemExit(f'format mismatch {stem} {percent} {s}')
        ref,aud=level_match(ref,aud)
        trial_dir=args.output/f'trial_{ti:02d}';trial_dir.mkdir(exist_ok=True)
        sf.write(trial_dir/'reference.wav',ref,ref_sr,subtype='FLOAT')
        order=list(systems);rng.shuffle(order)
        m={'trial':ti,'category':r['category'],'stem':stem,'semitones':float(r['semitones']),'reference':f'trial_{ti:02d}/reference.wav'}
        k={'trial':ti,'category':r['category'],'stem':stem,'semitones':float(r['semitones'])}
        for lab,system in zip(labels,order):
            fn=f'{lab}.wav';sf.write(trial_dir/fn,aud[system],ref_sr,subtype='FLOAT');m[lab]=f'trial_{ti:02d}/{fn}';k[lab]=system
        manifest.append(m);key.append(k)
    fields=['trial','category','stem','semitones','reference',*labels]
    with (args.output/'manifest.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(manifest)
    with (args.output/'answer_key.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=['trial','category','stem','semitones',*labels]);w.writeheader();w.writerows(key)
    write_html(args.output/'index.html',manifest,labels)
    (args.output/'README.txt').write_text('Open index.html in a browser. Listen against Reference, choose the best anonymous render, export choices.csv, then inspect answer_key.csv only after finishing. Audio is evaluation-only and should not be committed.\n')
    print(f'wrote {len(manifest)} trials to {args.output}')
if __name__=='__main__':main()
