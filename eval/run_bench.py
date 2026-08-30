#!/usr/bin/env python3
from pathlib import Path
import argparse,subprocess
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--bench',default=str(ROOT/'build'/'boiled_egg_bench'));args=ap.parse_args();out=ROOT/'results'/'realtime_bench.csv';out.parent.mkdir(exist_ok=True);p=subprocess.run([args.bench],check=True,capture_output=True,text=True);out.write_text(p.stdout);print(p.stdout)
