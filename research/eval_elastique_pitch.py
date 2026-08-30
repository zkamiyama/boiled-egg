#!/usr/bin/env python3
from __future__ import annotations
import argparse, concurrent.futures as cf, csv, json, math, re, subprocess
from collections import defaultdict
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal

EPS=1e-12
PAT=re.compile(r'^(?P<stem>.+)_Elastique_(?P<percent>[0-9.]+)_per\.wav$')
MODES=('off','harmonic','monophonic')

def feat(x,sr):
    if x.ndim>1:x=np.mean(x,axis=1)
    target=16000
    if sr!=target:
        g=math.gcd(int(sr),target); x=signal.resample_poly(x,target//g,int(sr)//g)
    x=np.asarray(x,dtype=np.float64); sr=target;nfft=1024;hop=256
    f,_,z=signal.stft(x,fs=sr,window='hann',nperseg=nfft,noverlap=nfft-hop,nfft=nfft,boundary='zeros',padded=True)
    mag=np.abs(z)+1e-8;logm=np.log(mag)
    full=np.concatenate([logm,logm[-2:0:-1]],axis=0);c=np.fft.ifft(full,axis=0).real;q=24
    keep=np.zeros_like(c);keep[:q+1]=c[:q+1];keep[-q:]=c[-q:]
    env=np.fft.fft(keep,axis=0).real[:len(f)]*(20/math.log(10))
    norm=logm-np.mean(logm,axis=0,keepdims=True)
    onset=np.mean(np.maximum(0,np.diff(norm,axis=1,prepend=norm[:,:1])),axis=0)
    return f,env,onset

def imat(x,n):
    if x.shape[1]==n:return x
    return np.vstack([np.interp(np.linspace(0,1,n),np.linspace(0,1,x.shape[1]),r) for r in x])
def ivec(x,n):return x if len(x)==n else np.interp(np.linspace(0,1,n),np.linspace(0,1,len(x)),x)
def corr(a,b):
    a=a-np.mean(a);b=b-np.mean(b);d=np.linalg.norm(a)*np.linalg.norm(b)
    return float(np.clip(np.dot(a,b)/d,-1,1)) if d>EPS else 1.0

def metrics(ref,y,sr):
    rf,re,ro=feat(ref,sr);_,te,to=feat(y,sr);n=max(re.shape[1],te.shape[1]);a=imat(re,n);b=imat(te,n);ao=ivec(ro,n);bo=ivec(to,n)
    mask=(rf>=150)&(rf<=6000);a=a[mask];b=b[mask];b+=np.median(a-b,axis=0,keepdims=True)
    env=float(np.sqrt(np.mean((a-b)**2)))
    rms=float(np.sqrt(np.mean(np.asarray(y,dtype=np.float64)**2)+EPS));peak=float(np.max(np.abs(y)))
    return env,corr(ao,bo),rms,peak

def exact_resample(x,n):
    if len(x)==n:return np.asarray(x,dtype=np.float32)
    return signal.resample(np.asarray(x,dtype=np.float64),n,axis=0).astype(np.float32)

def render(cli,src,dst,ratio,formant,pv_mode,fft_size,hop):
    cmd=[str(cli),str(src),str(dst),'--time','1','--pitch-ratio',f'{ratio:.12g}','--mode',pv_mode,'--formant',formant,'--fft',str(fft_size),'--hop',str(hop)]
    p=subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
    if p.returncode: raise RuntimeError(p.stderr)

def category(stem):
    if stem.startswith(('Male_','Female_','Child_')) or stem=='You_mean_this_one':return 'voice'
    if stem in {'Ardour_2','Jazz_3','Rock_4','Brass_and_perc_9'}:return 'mix'
    if stem in {'Oboe_piano_1','Saxophones_6','Woodwinds_4'}:return 'polyphonic'
    return 'solo'

def process_condition(args):
    cli,ref_dir,test_path,out_dir,pv_mode,fft_size,hop,modes=args
    m=PAT.match(test_path.name); stem=m.group('stem')
    ref_path=ref_dir/f'{stem}.wav'; ref,sr=sf.read(ref_path,always_2d=True,dtype='float32'); el,sr2=sf.read(test_path,always_2d=True,dtype='float32')
    if sr2!=sr:raise RuntimeError('sample rate mismatch')
    ratio=len(el)/len(ref); semitones=12*math.log2(ratio)
    cdir=out_dir/stem/f'{m.group("percent")}_per';cdir.mkdir(parents=True,exist_ok=True)
    elp=exact_resample(el,len(ref)); sf.write(cdir/'elastique.wav',elp,sr,subtype='FLOAT')
    rows=[]
    env,on,rms,peak=metrics(ref,elp,sr)
    rows.append(dict(stem=stem,category=category(stem),percent=float(m.group('percent')),pitch_ratio=ratio,semitones=semitones,system='elastique',env_rmse_db=env,onset_corr=on,rms=rms,peak=peak,duration_error_frames=len(elp)-len(ref)))
    for mode in modes:
        dst=cdir/f'boiled_{mode}.wav';render(cli,ref_path,dst,ratio,mode,pv_mode,fft_size,hop); y,ysr=sf.read(dst,always_2d=True,dtype='float32')
        env,on,rms,peak=metrics(ref,y,ysr)
        rows.append(dict(stem=stem,category=category(stem),percent=float(m.group('percent')),pitch_ratio=ratio,semitones=semitones,system=mode,env_rmse_db=env,onset_corr=on,rms=rms,peak=peak,duration_error_frames=len(y)-len(ref)))
    return rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cli',type=Path,required=True);ap.add_argument('--ref-dir',type=Path,required=True);ap.add_argument('--test-dir',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--workers',type=int,default=4);ap.add_argument('--pv-mode',choices=('locked','transient'),default='locked');ap.add_argument('--fft',type=int,default=2048);ap.add_argument('--hop',type=int);ap.add_argument('--formants',default='off,harmonic,monophonic');a=ap.parse_args();a.hop=a.hop or a.fft//8;modes=tuple(x.strip() for x in a.formants.split(',') if x.strip());bad=set(modes)-set(MODES);
    if bad: raise SystemExit(f'unknown formant modes: {sorted(bad)}')
    a.output.mkdir(parents=True,exist_ok=True);tests=sorted(a.test_dir.glob('*_Elastique_*_per.wav'));jobs=[(a.cli,a.ref_dir,p,a.output/'renders',a.pv_mode,a.fft,a.hop,modes) for p in tests];rows=[]
    with cf.ProcessPoolExecutor(max_workers=a.workers) as ex:
        for i,r in enumerate(ex.map(process_condition,jobs),1):rows.extend(r);print(f'condition {i}/{len(jobs)}',flush=True)
    csvp=a.output/'metrics.csv'
    with csvp.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    by=defaultdict(dict)
    for r in rows:by[(r['stem'],r['percent'])][r['system']]=r
    summary={'pv_mode':a.pv_mode,'fft_size':a.fft,'analysis_hop':a.hop,'conditions':len(by),'pitch_range_semitones':[min(d['elastique']['semitones'] for d in by.values()),max(d['elastique']['semitones'] for d in by.values())],'systems':{}}
    for mode in modes:
        e=[];o=[];wins=0;ow=0;cats=defaultdict(list)
        for d in by.values():
            de=d[mode]['env_rmse_db']-d['elastique']['env_rmse_db'];do=d[mode]['onset_corr']-d['elastique']['onset_corr'];e.append(de);o.append(do);wins+=de<0;ow+=do>0;cats[d[mode]['category']].append(de)
        summary['systems'][mode]=dict(mean_env_delta_vs_elastique_db=float(np.mean(e)),median_env_delta_vs_elastique_db=float(np.median(e)),env_wins_vs_elastique=wins,env_losses_vs_elastique=len(e)-wins,mean_onset_corr_delta_vs_elastique=float(np.mean(o)),onset_wins_vs_elastique=ow,by_category={c:{'mean_env_delta_db':float(np.mean(v)),'wins':sum(x<0 for x in v),'cases':len(v)} for c,v in cats.items()})
    summary['max_duration_error_frames']=max(abs(r['duration_error_frames']) for r in rows)
    (a.output/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True));print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=='__main__':main()
