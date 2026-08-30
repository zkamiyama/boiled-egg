#!/usr/bin/env python3
from pathlib import Path
import argparse,csv,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];ap=argparse.ArgumentParser();ap.add_argument('--corpus',default=str(ROOT/'data/external'));ap.add_argument('--cli',default=str(ROOT/'build/release/boiled_egg_cli'));ap.add_argument('--limit',type=int,default=8);ap.add_argument('--time',type=float,default=1.25);ap.add_argument('--pitch',type=float,default=5.0);args=ap.parse_args();root=Path(args.corpus);out=ROOT/'results'/'external'/'systems';out.mkdir(parents=True,exist_ok=True);sources=sorted(p for p in root.rglob('*.wav'))[:args.limit];rubberband=shutil.which('rubberband');ffmpeg=shutil.which('ffmpeg');rows=[]
for i,src in enumerate(sources):
 stem=f'{i:03d}_{src.stem}';be=out/f'{stem}__boiled_egg.wav';subprocess.run([args.cli,str(src),str(be),'--time',str(args.time),'--pitch',str(args.pitch)],check=True);rows.append([str(src),'boiled_egg',str(be),args.time,args.pitch])
 if rubberband:
  rb=out/f'{stem}__rubberband.wav';subprocess.run([rubberband,'-t',str(args.time),'-p',str(args.pitch),str(src),str(rb)],check=True);rows.append([str(src),'rubberband',str(rb),args.time,args.pitch])
 elif ffmpeg:
  rb=out/f'{stem}__rubberband_ffmpeg.wav';filt=f'rubberband=tempo={args.time}:pitch={2**(args.pitch/12)}';q=subprocess.run([ffmpeg,'-y','-loglevel','error','-i',str(src),'-af',filt,str(rb)])
  if q.returncode==0:rows.append([str(src),'rubberband_ffmpeg',str(rb),args.time,args.pitch])
manifest=ROOT/'results'/'external'/'render_manifest.csv';manifest.parent.mkdir(parents=True,exist_ok=True)
with manifest.open('w',newline='') as f:w=csv.writer(f);w.writerow(['source','system','render','time_ratio','pitch_st']);w.writerows(rows)
print(manifest)
