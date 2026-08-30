#!/usr/bin/env python3
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'data'/'generated'; out.mkdir(parents=True,exist_ok=True)
wav=out/'speech.wav'
cmd=['espeak-ng','-w',str(wav),'This is a local synthetic speech fixture for boiled egg pitch shifting and time stretching evaluation.']
try:
    subprocess.run(cmd,check=True)
    print(wav)
except FileNotFoundError:
    raise SystemExit('espeak-ng not found; install it or place speech/music under data/external/')
