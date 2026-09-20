#!/usr/bin/env python3
"""R2a: actual NSDGT -> independent paper-based phase -> dual synthesis.

Fixed-window PVDR baseline and an explicitly separate irregular-hop extension.
Not SELEBI, author's binary reproduction, pitch shifting or product promotion.
"""
from __future__ import annotations
import argparse
import ctypes as ct
import hashlib
import itertools
import json
import math
from pathlib import Path
import resource
import sys
import time
import zlib
import numpy as np
import scipy
import soundfile as sf
import comparison_contract as contract
import nsdgt_foundation as nsg
import offline_pv_benchmark as metrics

BASE='3a933a043561b11232cb894c12f6ff18daf62f24'
PROTOCOL='9a4037c06481865961ebd55e7922edbc246830b7'
FAMILIES=('tone61','tone1000','chirp','impulse','impulse1000','harmonic_impulse','decay50','decay50plus1000')
ALPHAS=(1,2,4)
SCHEDULES=('fixed','irregular_extension')
METHODS=('pv_backward_no_ipl','pvdr_paper_profile')
RATE=22050
REPEATS=3
class Config(ct.Structure):
    _fields_=[(k,ct.c_uint32) for k in ('struct_size','fft_size','frame_count','method')]+[
        ('stretch',ct.c_double),('relative_tolerance',ct.c_double),('seed',ct.c_uint64),('memory_limit_bytes',ct.c_uint64)]
class Info(ct.Structure):
    _fields_=[(k,ct.c_uint64) for k in ('temporal_edges','frequency_edges','low_bins','workspace_estimate_bytes')]+[
        ('maximum_magnitude_error',ct.c_double),('maximum_hermitian_correction',ct.c_double)]

def digest(x,dtype):return hashlib.sha256(np.ascontiguousarray(x,dtype=dtype).tobytes()).hexdigest()

class Phase:
    def __init__(self,path,sha):
        p=Path(path).resolve(strict=True)
        if contract.fingerprint(p)!=sha:raise ValueError('phase library hash mismatch')
        self.lib=ct.CDLL(str(p));self.fn=self.lib.be_phase_process
        self.fn.argtypes=[ct.POINTER(Config),ct.POINTER(ct.c_int64),ct.c_uint64,nsg.P,ct.c_uint64,
            nsg.P,ct.c_uint64,ct.POINTER(ct.c_int32),nsg.D,nsg.D,ct.c_uint64,ct.POINTER(Info)]
        self.fn.restype=ct.c_int
    def __call__(self,z,m,centers,alpha,method,seed=20260920,budget=512*1024*1024):
        raw=np.asarray(z)
        if method not in METHODS or not math.isfinite(alpha) or not 1<=alpha<=4:raise ValueError('scope/method')
        if type(m)!=int or m<16 or m>16384 or m&(m-1):raise ValueError('FFT shape')
        if not 2<=len(centers)<=4096 or len(centers)*m>8388608:raise ValueError('coefficient budget')
        if raw.ndim!=1 or raw.size!=len(centers)*m or not np.isfinite(raw).all():raise ValueError('bad coefficient shape')
        if any(type(a)!=int or not 0<=a<288000 for a in centers):raise ValueError('bad center')
        x=np.ascontiguousarray(raw,dtype=np.complex64)
        if not np.isfinite(x).all():raise ValueError('float overflow')
        a=np.ascontiguousarray(centers,dtype=np.int64);q=len(a)*(m//2+1)
        out=np.full_like(x,-99+11j);pred=np.full(q,-99,dtype=np.int32);dt=np.full(q,-99.);df=dt.copy();info=Info()
        c=Config(ct.sizeof(Config),m,len(a),METHODS.index(method),alpha,1e-6,seed,budget)
        start=time.perf_counter()
        rc=self.fn(ct.byref(c),a.ctypes.data_as(ct.POINTER(ct.c_int64)),len(a),x.ctypes.data_as(nsg.P),len(x),
            out.ctypes.data_as(nsg.P),len(out),pred.ctypes.data_as(ct.POINTER(ct.c_int32)),dt.ctypes.data_as(nsg.D),
            df.ctypes.data_as(nsg.D),q,ct.byref(info))
        elapsed=time.perf_counter()-start
        if rc:
            if not np.all(out==np.complex64(-99+11j)) or not np.all(pred==-99) or not np.all(dt==-99) or not np.all(df==-99):
                raise RuntimeError('partial writes on failure')
            raise ValueError(f'phase rejection:{rc}')
        if not np.isfinite(out).all():raise ValueError('nonfinite phase output')
        return out,pred,dt,df,{k:getattr(info,k) for k,_ in info._fields_},elapsed


def fixture(name,alpha=1):
    if name not in FAMILIES or alpha not in ALPHAS:raise ValueError('unknown fixture')
    length=RATE*alpha;t=np.arange(length)/RATE;source_t=t/alpha
    fade=np.minimum(1,np.minimum(source_t/.02,(1-source_t)/.02))
    out=np.zeros(length);center=round(.4*RATE)*alpha
    tones=[]
    if name=='tone61':tones=[(61.,.2)]
    elif name=='tone1000':tones=[(1000.,.2)]
    elif name=='chirp':out=.15*np.sin(2*np.pi*(61*t+400*t*t/alpha))*fade
    elif name in ('impulse1000','decay50plus1000'):tones=[(1000.,.25)]
    elif name=='harmonic_impulse':tones=[(1000.,.25),(2000.,.125),(3000.,.0625)]
    for f,amp in tones:out+=amp*np.sin(2*np.pi*f*t)*fade
    if 'impulse' in name:out[center]+=.5
    if name.startswith('decay'):
        v=np.arange(length-center)/RATE;out[center:]+=.5*np.exp(-v/.03)*np.cos(2*np.pi*50*v)
    return np.asarray(out,dtype=np.float32),dict(family=name,rate=RATE,n=length,alpha=alpha,
        center=center if 'impulse' in name or name.startswith('decay') else None,tones=tones)


def schedule(length,alpha,name):
    if alpha not in ALPHAS or name not in SCHEDULES:raise ValueError('schedule scope')
    hop=128//alpha;centers=[];a=0;j=0
    while a<length:
        centers.append(a)
        a+=hop if name=='fixed' else (hop,hop//2,hop,3*hop//4)[j%4]
        j+=1
    centers=sorted(set(centers+[length-1]))
    return centers,[np.hanning(2048) for _ in centers]


def spectral_error(y,truth,center):
    # Eq13-type error with an explicit independent fixed evaluation transform.
    # No fitting, alignment, gain normalization or output clipping.
    window=np.hanning(2048);numerator=denominator=0.;local_n=local_d=0.
    for a in range(0,len(y),128):
        ix=np.arange(a-1024,a+1024);ok=(ix>=0)&(ix<len(y))
        yy=np.zeros(2048);tt=np.zeros(2048);yy[ok]=y[ix[ok]];tt[ok]=truth[ix[ok]]
        ys=np.abs(np.fft.rfft(yy*window));ts=np.abs(np.fft.rfft(tt*window))
        # rFFT Hermitian energy multiplicity: equivalent to the full DFT Frobenius norm.
        weights=np.full(1025,2.);weights[0]=weights[-1]=1.
        num=float(np.dot(weights,(ys-ts)**2));den=float(np.dot(weights,ts**2))
        numerator+=num;denominator+=den
        if center is not None and abs(a-center)<=round(.1*RATE):local_n+=num;local_d+=den
    return dict(full=float(np.sqrt(numerator/denominator)),
        event=None if not local_d else float(np.sqrt(local_n/local_d)),window=2048,hop=128,fft=2048)


def event_diagnostics(y,truth,center):
    lo=max(0,center-round(.1*RATE));hi=min(len(y),center+round(.1*RATE)+1)
    def one(x):
        e=np.asarray(x[lo:hi],dtype=float)**2;total=float(e.sum())
        if total<=1e-18:return dict(energy=total,centroid_error_ms=None,width_ms=None)
        quantile=np.searchsorted(np.cumsum(e)/total,[.05,.95])
        return dict(energy=total,centroid_error_ms=float(np.dot(e,np.arange(lo,hi)-center)/total*1000/RATE),
                    width_ms=float((quantile[1]-quantile[0])*1000/RATE))
    measured=one(y);oracle=one(truth)
    measured['oracle']=oracle
    measured['energy_error_db']=float(10*np.log10(max(measured['energy'],1e-30)/oracle['energy']))
    measured['outside_window_energy']=float(np.sum(np.asarray(y[:lo],dtype=float)**2)+np.sum(np.asarray(y[hi:],dtype=float)**2))
    # Centroid is not onset for a causal decay or an unresolved full-band mixture.
    measured['centroid_vs_oracle_ms']=None if measured['centroid_error_ms'] is None else measured['centroid_error_ms']-oracle['centroid_error_ms']
    return measured


def measure(x,y,meta,alpha):
    y=np.asarray(y)
    if len(y)!=len(x)*alpha or not np.isfinite(y).all() or not np.any(y):raise ValueError('invalid output length/finite/nonzero')
    truth,target=fixture(meta['family'],alpha);v=y.real.astype(float)
    result=dict(peak=float(np.max(np.abs(v))),rms=float(np.sqrt(np.mean(v*v))),imaginary_peak=float(np.max(np.abs(y.imag))),
                spectral=spectral_error(v,truth,target['center']))
    if alpha==1:
        result['identity']=dict(max_error=float(np.max(np.abs(y-x))),relative_l2=float(np.linalg.norm(y-x)/np.linalg.norm(x)))
    if meta['family'] in ('tone61','tone1000'):
        f,amp=target['tones'][0];part=v[round(.15*RATE*alpha):round(.85*RATE*alpha)]
        amplitudes,residual=metrics.components(part,RATE,[f])
        cents=metrics.tone_error(part,RATE,f);db=float(20*np.log10(max(amplitudes[0],1e-30)/amp))
        result['tone']=dict(cents=cents,amplitude_error_db=db,unexplained_energy=residual,
                            passed=abs(cents)<=5 and abs(db)<=1 and residual<=.01)
    if target['center'] is not None:result['event']=event_diagnostics(v,truth,target['center'])
    return result


def prepare(phase_path,nsg_path,out):
    out.mkdir(parents=True,exist_ok=False)
    files=metrics.file_map(Path(__file__).resolve().parents[1]);files.update(metrics.binary_map(phase_path));files.update(metrics.binary_map(nsg_path))
    inputs=[]
    for family in FAMILIES:
        x,meta=fixture(family);path=out/(family+'.npy');np.save(path,x,allow_pickle=False)
        inputs.append(dict(path=str(path.resolve()),sha256=contract.fingerprint(path),metadata=meta))
    contract.json_write(out/'plan.json',dict(schema='pvdr-r2a-v1',base=BASE,protocol_commit=PROTOCOL,
        phase_library=str(phase_path.resolve()),nsdgt_library=str(nsg_path.resolve()),files=files,inputs=inputs,
        alphas=list(ALPHAS),schedules=list(SCHEDULES),methods=list(METHODS),repeats=REPEATS,cells=96,renders=288,
        seed=20260920,tolerance=1e-6,environment=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,soundfile=sf.__version__),
        data_scope='declared synthetic signals; not author original data or independent natural-audio confirmation',quality_selection=None))


def identity(plan):
    if plan['schema']!='pvdr-r2a-v1' or plan['alphas']!=list(ALPHAS) or plan['methods']!=list(METHODS) or plan['schedules']!=list(SCHEDULES) or plan['repeats']!=REPEATS:
        raise ValueError('changed registered grid')
    families=[v['metadata']['family'] for v in plan['inputs']]
    if len(families)!=len(set(families)) or set(families)!=set(FAMILIES):raise ValueError('incomplete input grid')
    for path,sha in plan['files'].items():
        if contract.fingerprint(Path(path))!=sha:raise ValueError('changed source/binary/dependency')
    for v in plan['inputs']:
        if contract.fingerprint(Path(v['path']))!=v['sha256']:raise ValueError('changed input')


def key(r):return tuple(r[k] for k in ('family','alpha','schedule','method','repeat'))

def assess(rows):
    expected=set(itertools.product(FAMILIES,ALPHAS,SCHEDULES,METHODS,range(REPEATS)))
    keys=[key(r) for r in rows]
    if len(keys)!=len(set(keys)) or set(keys)!=expected:raise ValueError('incomplete/duplicate output grid')
    complete=all(r['status']=='complete' for r in rows)
    report=dict(attempts=len(rows),complete=complete,quality_selection=None,profiles=None)
    if not complete:return dict(**report,integrity_pass=False,decision='blocked_execution')
    # A complete status alone is not evidence; malformed/nonfinite receipts fail closed.
    def finite_tree(value):
        if isinstance(value,dict):return all(finite_tree(v) for v in value.values())
        if isinstance(value,list):return all(finite_tree(v) for v in value)
        return math.isfinite(value) if isinstance(value,(int,float)) else True
    required=('pcm_sha256','coeff_sha256','phase_coeff_sha256','trace_sha256','dt_sha256','df_sha256')
    try:
        for r in rows:
            if not finite_tree(r):raise ValueError('nonfinite receipt')
            for name in required:
                value=r[name]
                if not isinstance(value,str) or len(value)!=64 or any(v not in '0123456789abcdef' for v in value):
                    raise ValueError('invalid identity')
            for name in ('maximum_magnitude_error',):float(r['native'][name])
            for name in ('peak','imaginary_peak'):float(r['metrics'][name])
            if not isinstance(r['metrics']['spectral'],dict):raise ValueError('missing spectral diagnostics')
            if r['alpha']==1:float(r['metrics']['identity']['relative_l2'])
    except (KeyError,TypeError,ValueError):
        return dict(**report,integrity_pass=False,decision='blocked_malformed_receipt')
    cells={}
    for r in rows:cells.setdefault(key(r)[:-1],[]).append(r)
    repeat=all(len({(v['pcm_sha256'],v['coeff_sha256'],v['phase_coeff_sha256'],v['trace_sha256'],v['dt_sha256'],v['df_sha256']) for v in rr})==1 for rr in cells.values())
    integrity=repeat and all(r['native']['maximum_magnitude_error']<=3e-6 and r['metrics']['imaginary_peak']<=3e-6*max(1.,r['metrics']['peak']) for r in rows)
    profiles={}
    for schedule_name,method in itertools.product(SCHEDULES,METHODS):
        rr=[r for r in rows if r['repeat']==0 and r['schedule']==schedule_name and r['method']==method]
        tone=[r for r in rr if 'tone' in r['metrics']];ids=[r for r in rr if r['alpha']==1]
        profiles[schedule_name+'/'+method]=dict(cells=len(rr),tone_pass=sum(r['metrics']['tone']['passed'] for r in tone),tone_cells=len(tone),
            maximum_identity_l2=max(r['metrics']['identity']['relative_l2'] for r in ids),
            nonidentity_spectral_errors=[dict(family=r['family'],alpha=r['alpha'],**r['metrics']['spectral']) for r in rr if r['alpha']!=1])
    return dict(attempts=len(rows),complete=True,integrity_pass=integrity,repeats_identical=repeat,quality_selection=None,
                profiles=profiles,decision='reference_profile_only_not_product_promotion')


def run(planpath,sha,out):
    if contract.fingerprint(planpath)!=sha:raise ValueError('plan hash mismatch')
    plan=json.loads(planpath.read_text());identity(plan);out.mkdir(parents=True,exist_ok=False);objects=out/'objects';objects.mkdir()
    phase=Phase(plan['phase_library'],plan['files'][plan['phase_library']]);native=nsg.Native(plan['nsdgt_library'],plan['files'][plan['nsdgt_library']])
    rows=[]
    for source,alpha,sched,method in itertools.product(plan['inputs'],ALPHAS,SCHEDULES,METHODS):
        x=np.load(source['path'],allow_pickle=False);centers,windows=schedule(len(x),alpha,sched);m=2048*alpha
        analysis=nsg.pack(len(x),m,centers,windows,budget=512*1024*1024)
        synthesis=nsg.pack(len(x)*alpha,m,[alpha*a for a in centers],windows,budget=512*1024*1024)
        for repeat in range(REPEATS):
            row=dict(family=source['metadata']['family'],alpha=alpha,schedule=sched,method=method,repeat=repeat,status='failed',errors=[])
            try:
                start=time.perf_counter();z,ai,ta=native.call(True,x,analysis)
                zz,pred,dt,df,info,tp=phase(z,m,centers,alpha,method)
                y,si,ts=native.call(False,zz,synthesis);elapsed=time.perf_counter()-start
                measured=measure(x,y,source['metadata'],alpha)
                raw=np.asarray(y,dtype='<c8').tobytes();ph=hashlib.sha256(raw).hexdigest();path=objects/(ph+'.c64')
                if not path.exists():path.write_bytes(raw)
                tr=np.asarray(pred,dtype='<i4').tobytes();th=hashlib.sha256(tr).hexdigest();trace=objects/(th+'.trace.zlib')
                if not trace.exists():trace.write_bytes(zlib.compress(tr,9))
                row.update(status='complete',pcm_sha256=ph,output=str(path.relative_to(out)),trace_sha256=th,trace=str(trace.relative_to(out)),
                    coeff_sha256=digest(z,'<c8'),phase_coeff_sha256=digest(zz,'<c8'),dt_sha256=digest(dt,'<f8'),df_sha256=digest(df,'<f8'),
                    native=info,analysis_info=ai,synthesis_info=si,frames=len(centers),fft=m,
                    timing=dict(analysis=ta,phase=tp,synthesis=ts,total=elapsed),metrics=measured)
                del z,zz,pred,dt,df,y
            except (ValueError,RuntimeError,OSError) as exc:row['status']='failed';row['errors']=[str(exc)]
            rows.append(row)
            with (out/'rows.jsonl').open('a') as stream:stream.write(json.dumps(row,allow_nan=False)+'\n')
        print(f'{len(rows)}/288 {source["metadata"]["family"]} alpha{alpha} {sched} {method}',flush=True)
    identity(plan);summary=assess(rows);summary.update(rows=rows,plan_sha256=sha,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    contract.json_write(out/'summary.json',summary);return summary


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='cmd',required=True)
    a=s.add_parser('prepare');a.add_argument('--phase',type=Path,required=True);a.add_argument('--nsdgt',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('run');a.add_argument('--plan',type=Path,required=True);a.add_argument('--sha256',required=True);a.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.cmd=='prepare':prepare(args.phase,args.nsdgt,args.output);print(contract.fingerprint(args.output/'plan.json'));return 0
    return 0 if run(args.plan,args.sha256,args.output)['integrity_pass'] else 2
if __name__=='__main__':raise SystemExit(main())
