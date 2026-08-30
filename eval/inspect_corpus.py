#!/usr/bin/env python3
from pathlib import Path
import argparse
import soundfile as sf
ap=argparse.ArgumentParser();ap.add_argument('root',nargs='?',default='data/external');args=ap.parse_args();root=Path(args.root)
files=sorted(p for p in root.rglob('*') if p.suffix.lower() in {'.wav','.flac','.aif','.aiff','.ogg'})
print('path,sample_rate,channels,frames,seconds')
for p in files:
 try:
  i=sf.info(p); print(f'{p},{i.samplerate},{i.channels},{i.frames},{i.duration:.3f}')
 except Exception as e: print(f'# skip {p}: {e}')
print(f'# files={len(files)}')
