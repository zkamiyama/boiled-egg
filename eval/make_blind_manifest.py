#!/usr/bin/env python3
from pathlib import Path
import argparse,csv,hashlib,random
ap=argparse.ArgumentParser();ap.add_argument('root');ap.add_argument('--out',default='results/external/blind_manifest.csv');ap.add_argument('--seed',type=int,default=20260830);args=ap.parse_args();root=Path(args.root);files=sorted(root.rglob('*.wav'));rng=random.Random(args.seed);items=[]
for p in files:
 token=hashlib.sha256((str(p)+str(args.seed)).encode()).hexdigest()[:12];items.append([token,str(p)])
rng.shuffle(items);out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
with out.open('w',newline='') as f:w=csv.writer(f);w.writerow(['trial_id','source_path']);w.writerows(items)
print(out)
