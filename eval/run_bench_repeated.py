#!/usr/bin/env python3
from pathlib import Path
import argparse,csv,subprocess
ROOT=Path(__file__).resolve().parents[1];ap=argparse.ArgumentParser();ap.add_argument('--bench',default=str(ROOT/'build/release/boiled_egg_bench'));ap.add_argument('--runs',type=int,default=5);args=ap.parse_args();rows=[]
for run in range(args.runs):
 p=subprocess.run([args.bench],check=True,capture_output=True,text=True);rs=list(csv.DictReader(p.stdout.splitlines()));
 for r in rs:r['run']=run+1;rows.append(r)
out=ROOT/'results'/'realtime_bench_repeated.csv';out.parent.mkdir(exist_ok=True);fields=['run']+[x for x in rows[0] if x!='run']
with out.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
worst=max(rows,key=lambda r:float(r['p99_deadline_fraction']));print(f"worst={worst['p99_deadline_fraction']} run={worst['run']} sr={worst['sample_rate']} block={worst['block']} pitch={worst['pitch_st']}")
