#!/usr/bin/env python3
from pathlib import Path
import argparse,csv,subprocess
import numpy as np
import soundfile as sf
ROOT=Path(__file__).resolve().parents[1]
def peak_hz(x,sr,lo=100,hi=4000):
 x=x[len(x)//4:3*len(x)//4]; X=np.abs(np.fft.rfft(x*np.hanning(len(x)))); f=np.fft.rfftfreq(len(x),1/sr); m=(f>=lo)&(f<=hi); return float(f[m][np.argmax(X[m])])
def corr(a,b):
 n=min(len(a),len(b)); a=a[:n]-np.mean(a[:n]); b=b[:n]-np.mean(b[:n]); return float(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)+1e-12))
def middle_rms(x,sr):
 trim=min(sr//2,max(0,len(x)//4)); y=x[trim:len(x)-trim] if len(x)>2*trim else x; return float(np.sqrt(np.mean(np.square(y))) if len(y) else 0.0)
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--cli',default=str(ROOT/'build'/'boiled_egg_cli')); args=ap.parse_args(); cli=Path(args.cli); outdir=ROOT/'results'/'synthetic'; outdir.mkdir(parents=True,exist_ok=True)
 cases=[('identity','harmonic_stack.wav',1,0),('stretch_075','harmonic_stack.wav',.75,0),('stretch_150','harmonic_stack.wav',1.5,0),('pitch_m12','sine_440.wav',1,-12),('pitch_p12','sine_440.wav',1,12),('pitch_p12_passband','sine_10000.wav',1,12),('pitch_p12_stopband','sine_14000.wav',1,12),('combo','synthetic_drums.wav',1.25,5),('stereo','stereo_phase.wav',1,7)]; rows=[]
 for name,src,tr,ps in cases:
  inp=ROOT/'data'/'synthetic'/src; out=outdir/f'{name}.wav'; subprocess.run([str(cli),str(inp),str(out),'--time',str(tr),'--pitch',str(ps)],check=True,capture_output=True,text=True); x,sr=sf.read(inp,always_2d=True); y,sro=sf.read(out,always_2d=True); expected=round(len(x)*tr); row={'case':name,'input_frames':len(x),'output_frames':len(y),'expected_frames':expected,'duration_error_frames':len(y)-expected}
  if name in {'pitch_m12','pitch_p12'}:
   f=peak_hz(y[:,0],sr); target=440*(2**(ps/12)); row['peak_hz']=f; row['pitch_error_cents']=1200*np.log2(f/target)
  if name in {'pitch_p12_passband','pitch_p12_stopband'}: row['middle_rms']=middle_rms(y[:,0],sr)
  if name=='identity': row['identity_corr']=corr(x[:,0],y[:,0])
  if name=='stereo': row['stereo_lr_corr']=corr(y[:,0],y[:,1]); row['stereo_corr_error']=row['stereo_lr_corr']-corr(x[:,0],x[:,1])
  rows.append(row)
 d={r['case']:r for r in rows}; p=d['pitch_p12_passband']['middle_rms'];q=d['pitch_p12_stopband']['middle_rms'];d['pitch_p12_stopband']['alias_rejection_db']=20*np.log10(max(q,1e-15)/max(p,1e-15));fields=sorted({k for r in rows for k in r})
 with open(outdir/'metrics.csv','w',newline='') as f: w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
if __name__=='__main__': main()
