#!/usr/bin/env python3
"""Frozen detector/shared-phase study; prior blocked evaluation files are not used.
Source-relative scores are not MOS. Event truth is supplied to scorers only.
"""
import argparse, concurrent.futures as cf, csv, hashlib, importlib.util, json, sys
from pathlib import Path
import numpy as np
import scipy
import soundfile as sf
from scipy import signal
from scipy.optimize import linear_sum_assignment
import recombine as r
import detection as d
_edges=Path(__file__).parents[1]/'phase_edges'
sys.path.insert(0,str(_edges))
_spec=importlib.util.spec_from_file_location('linked_existing_metrics',_edges/'study.py')
metrics=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(metrics)
sys.path.pop(0)
PILOT={'Ardour_2','Female_4','Male_6','Rock_4','Triangle_02'}
SPACINGS=(4,7,12,19,27,38,54,83)
SEEDS=tuple(range(26091580,26091588))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def pcm(x):return hashlib.sha256(np.ascontiguousarray(x,dtype='<f8').tobytes()).hexdigest()

def events_signal(rate,ratio=1.,spacing=.027,level=1.,same_channel=False,noise=False,
                  mixed=False,seed=26091580,duration=.002):
    count=int(np.floor(1.85*rate*ratio+.5));out=np.zeros((count,2));truth=[];rng=np.random.default_rng(seed)
    for c in (0,1):
        for i,t in enumerate((.25,.65,1.05,1.45)):
            ch=0 if same_channel else c;center=(t+c*spacing)*ratio
            n=round(duration*rate);local=(np.arange(n)-n//2)/rate
            carrier=rng.normal(0,.18,n) if noise else sum(.07*np.cos(2*np.pi*f*local+i*.31) for f in (2503,4013,6809))
            burst=carrier*np.sin(np.pi*np.arange(n)/n)**2*(level if c else 1)
            lo=round(center*rate)-n//2;out[lo:lo+n,ch]+=burst;truth.append((center,ch,duration))
    if mixed:
        t=np.arange(count)/rate;freq=80+np.cumsum(rng.uniform(60,135,6));phase=rng.uniform(-np.pi,np.pi,6)
        for ch in (0,1):out[:,ch]+=sum(.023*np.sin(2*np.pi*f*t+p+.4*ch) for f,p in zip(freq,phase))
    return out,truth

def fixture(name,rate,ratio=1.,seed=26091580):
    if name in ('bank','low55'):
        n=int(np.floor(1.85*rate*ratio+.5));t=np.arange(n)/rate
        frequencies=np.array([55.]) if name=='low55' else np.array([110.,223.4,378.9,531.2,829.7,1193.2,2300.3,4113.1])
        x=sum(.05/np.sqrt(i+1)*np.sin(2*np.pi*f*t+i*.7) for i,f in enumerate(frequencies))
        return x[:,None],dict(frequencies=frequencies.tolist())
    if name=='mixture':
        index=seed-SEEDS[0];x,truth=events_signal(rate,ratio,SPACINGS[index]/1000,[1,.25,.063,.5][index%4],noise=True,mixed=True,seed=seed,duration=.006)
        return x,dict(events=truth,highpass=True)
    x,truth=events_signal(rate,ratio,spacing=.027 if name=='stagger27' else 0.,
        noise=name=='noise',duration=.02 if name=='wide20' else .006 if name=='noise' else .002)
    if name!='stagger27':x=x[:,0,None];truth=[v for v in truth if v[1]==0]
    return x,dict(events=truth,highpass=False)

def detection_score(estimated,truth,rate,tolerance_ms=2.):
    expected=np.unique(np.asarray([t[0] for t in truth])*rate)
    if len(estimated) and len(expected):
        dist=np.abs(expected[:,None]-estimated[None,:]);limit=rate*tolerance_ms/1000
        cost=np.where(dist<=limit,dist,1e12);a,b=linear_sum_assignment(cost);ok=dist[a,b]<=limit
        tp=int(ok.sum());error=float(dist[a[ok],b[ok]].max()*1000/rate) if tp else 0.
    else:tp=0;error=0.
    return dict(expected=len(expected),detected=len(estimated),tp=tp,fp=len(estimated)-tp,fn=len(expected)-tp,
        recall=tp/len(expected) if len(expected) else 1.,precision=tp/len(estimated) if len(estimated) else 0.,max_matched_error_ms=error)

def event_score(y,oracle,rate,events,highpass=False):
    if highpass:
        sos=signal.butter(6,1800,btype='highpass',fs=rate,output='sos')
        y=signal.sosfiltfilt(sos,y,axis=0);oracle=signal.sosfiltfilt(sos,oracle,axis=0)
    rows=[]
    for center,ch,duration in events:
        same=sorted(t for t,c,du in events if c==ch);index=same.index(center)
        # Per-channel Voronoi cells avoid scoring a close neighbor twice.
        lo=max(0.,center-.08,(same[index-1]+center)/2 if index else 0.)
        hi=min(len(y)/rate,center+.08,(center+same[index+1])/2 if index+1<len(same) else len(y)/rate)
        a,b=round(lo*rate),round(hi*rate);t=np.arange(a,b)/rate
        def describe(x):
            power=x[a:b,ch]**2;total=float(power.sum());safe=max(total,1e-30)
            width=np.diff(np.interp([.05,.95],np.cumsum(power)/safe,t))[0]*1000 if total>1e-24 else 0.
            centroid=float(np.dot(power,t)/safe) if total>1e-24 else center
            outside=float(power[np.abs(t-center)>duration/2+1/rate].sum()/safe)
            return width,centroid,total,outside
        wy,cy,ey,oy=describe(y);wq,cq,eq,oq=describe(oracle)
        rows.append((abs(wy-wq),abs(cy-cq)*1000,abs(10*np.log10(max(ey,1e-30)/max(eq,1e-30))),oy,wy,wq))
    a=np.asarray(rows)
    return dict(width_error_ms=float(a[:,0].mean()),centroid_error_ms=float(a[:,1].mean()),
        energy_error_db=float(a[:,2].mean()),outside_support_fraction=float(a[:,3].mean()),
        measured_width_ms=float(a[:,4].mean()),oracle_width_ms=float(a[:,5].mean()))

def detector_job(job):
    rate,spacing,level,same,mixed,lib=job
    x,truth=events_signal(rate,spacing=spacing/1000,level=level,same_channel=same,mixed=mixed)
    _,p,_=r.prior.separate(x,rate);rows=[]
    for mode in ('legacy40','global6','linked6'):
        estimated,stats=d.detect(p,rate,mode,lib)
        rows.append(dict(rate=rate,spacing_ms=spacing,level=level,same_channel=same,mixed=mixed,mode=mode,
            source_pcm_sha256=pcm(x),anchor_samples=estimated.tolist(),**detection_score(estimated,truth,rate)))
    return rows

def render_job(job):
    suite,name,rate,ratio,seed,path,heap,events=job
    if path:
        x,sr=sf.read(path,dtype='float64',always_2d=True)
        if sr!=rate:raise ValueError('source rate mismatch')
        oracle=meta=None
    else:x,_=fixture(name,rate,seed=seed);oracle,meta=fixture(name,rate,ratio,seed)
    input_hash=pcm(x);outputs,stats=r.render_set(x,rate,ratio,heap,events);rows=[]
    for mode in r.MODES:
        y=outputs[mode];row=dict(suite=suite,source=name,rate=rate,ratio=ratio,seed=seed,mode=mode,
            input_pcm_sha256=input_hash,output_pcm_sha256=pcm(y),frames=len(y),channels=y.shape[1],peak=float(abs(y).max()),
            rms_gain_db=float(10*np.log10(max(np.mean(y*y),1e-30)/max(np.mean(x*x),1e-30))),**stats[mode])
        if path:row.update(metrics.old.natural_metrics(x,y,rate,ratio),**metrics.local_spectral(x,y,rate,ratio))
        elif 'frequencies' in meta:row.update(metrics.old.partials(y[:,0],oracle[:,0],np.array(meta['frequencies']),rate))
        else:row.update(event_score(y,oracle,rate,meta['events'],meta['highpass']))
        if not path and ratio==1:row['unity_max_error']=float(abs(y-x).max())
        if mode=='shared_long' and np.max(abs(y-outputs['heap']))>2e-12:raise ValueError('shared recombination identity')
        rows.append(row)
    # Replay unchanged baseline code on every actual reference cell.
    if path:
        old_heap,_=r.base.render(x,rate,time=ratio,mode='heap',kernel_path=heap)
        old_split,_=r.prior.render(x,rate,ratio,mode='split_heap_anchor_power',kernel=heap)
        if not np.array_equal(old_heap,outputs['heap']) or not np.array_equal(old_split,outputs['independent_legacy']):
            raise ValueError('baseline replay changed')
    if pcm(x)!=input_hash:raise ValueError('mutated input')
    return rows

def write_csv(path,rows):
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=sorted(set().union(*(a.keys() for a in rows))))
        writer.writeheader();writer.writerows(rows)

def run(args):
    if args.output.exists() or not 1<=args.workers<=4:raise ValueError('new output/workers1..4')
    heap=args.heap.resolve(strict=True);events=args.events.resolve(strict=True)
    dependencies=[Path(__file__),Path(r.__file__),Path(d.__file__),Path(r.prior.__file__),Path(r.base.__file__),Path(metrics.__file__),Path(metrics.old.__file__),heap,events]
    hashes={str(p.resolve()):sha(p) for p in dependencies};sources={}
    if args.suite=='detector':
        jobs=[(rate,s,level,same,mixed,str(events)) for rate in (48000,96000) for s in SPACINGS
            for level in (1.,.1,10**(-30/20)) for same in (False,True) for mixed in (False,True)]
        expected=len(jobs)*3;worker=detector_job
    else:
        worker=render_job;jobs=[]
        if args.suite=='corpus':
            files=sorted(args.refs.glob('*.wav')) if args.refs else []
            if len(files)!=20:raise ValueError('actual20 reference files required')
            for p in files:
                sources[str(p.resolve())]=sha(p)
                for ratio in (.5,1.5,2.):jobs.append(('corpus',p.stem,sf.info(p).samplerate,ratio,0,str(p.resolve()),str(heap),str(events)))
        else:
            for seed in (SEEDS if args.suite=='mixtures' else (0,)):
                for name in (('mixture',) if args.suite=='mixtures' else ('bank','low55','narrow2','wide20','noise','stagger27')):
                    for rate in (48000,96000):
                        for ratio in ((.5,1.5,2.) if args.suite=='mixtures' else (.5,1.,1.5,2.)):
                            jobs.append((args.suite,name,rate,ratio,seed,None,str(heap),str(events)))
        expected=len(jobs)*len(r.MODES)
    manifest=dict(suite=args.suite,jobs=jobs,code=hashes,sources=sources)
    identity=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
    cache=args.output.parent/(args.output.name+'-journal');cache.mkdir(parents=True,exist_ok=True)
    header=cache/'manifest.json'
    if header.exists():
        if json.loads(header.read_text())!=json.loads(json.dumps(manifest)):raise ValueError('journal identity mismatch')
    elif any(cache.iterdir()):raise ValueError('unbound journal')
    else:header.write_text(json.dumps(manifest,indent=2)+'\n')
    parts={};missing=[]
    for i,job in enumerate(jobs):
        file=cache/f'{i:04}.json'
        if file.exists():
            blob=json.loads(file.read_text());payload=json.dumps(blob['rows'],sort_keys=True)
            if blob['identity']!=identity or blob['index']!=i or blob['sha256']!=hashlib.sha256(payload.encode()).hexdigest():raise ValueError('journal corrupt')
            parts[i]=blob['rows']
        else:missing.append((i,job))
    with cf.ProcessPoolExecutor(args.workers) as pool:
        for n,((i,_),rows) in enumerate(zip(missing,pool.map(worker,[job for i,job in missing])),1):
            payload=json.dumps(rows,sort_keys=True,allow_nan=False)
            blob=dict(identity=identity,index=i,rows=rows,sha256=hashlib.sha256(payload.encode()).hexdigest())
            tmp=cache/f'.{i:04}.tmp';tmp.write_text(json.dumps(blob,allow_nan=False)+'\n');tmp.replace(cache/f'{i:04}.json');parts[i]=rows
            if n%8==0:print(args.suite,n,'/',len(missing),flush=True)
    rows=[row for i in range(len(jobs)) for row in parts[i]]
    if len(rows)!=expected:raise ValueError('incomplete grid')
    for path,h in {**hashes,**sources}.items():
        if sha(path)!=h:raise ValueError('dependency/input changed')
    args.output.mkdir(parents=True)
    write_csv(args.output/'measurements.csv',rows)
    report=dict(suite=args.suite,rows=len(rows),generated_outputs=0 if args.suite=='detector' else len(rows),
        dependencies=hashes,sources=sources,identity=identity,measurements_sha256=sha(args.output/'measurements.csv'),
        numpy=np.__version__,scipy=scipy.__version__,soundfile=sf.__version__,
        baseline_replays=120 if args.suite=='corpus' else 0,
        notes='Frozen modes; no oracle input to detector/renderers. Source-relative metrics, not vendor/MOS. '
        'Shared-long is an algebraic control, not an independent quality improvement. Same corpus reused historically.')
    (args.output/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:report[k] for k in ('suite','rows','generated_outputs')}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('heap','events','output'):parser.add_argument('--'+arg,type=Path,required=True)
    parser.add_argument('--refs',type=Path)
    parser.add_argument('--suite',choices=('detector','synthetic','mixtures','corpus'),required=True)
    parser.add_argument('--workers',type=int,default=2)
    run(parser.parse_args())
