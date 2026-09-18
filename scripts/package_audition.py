#!/usr/bin/env python3
"""Create a minimal Linux application folder; no Qt/wheels/fonts/SDK are copied."""
from __future__ import annotations
import argparse
import hashlib
import json
import platform
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]

def package(output: Path, native: Path, sdk: Path) -> dict:
    output=output.resolve()
    if platform.system()!='Linux' or platform.machine() not in ('x86_64','AMD64'):
        raise ValueError('This packaging target is Linux x86_64 only')
    if output.exists():raise FileExistsError('Use a new package directory')
    copies={ROOT/'run_audition.py':Path('run_audition.py'),
            ROOT/'requirements-audition.txt':Path('requirements-audition.txt'),
            ROOT/'apps/audition/README.md':Path('README_JA.md'),
            native.resolve():Path('lib/libboiled_egg_transport.so'),
            sdk.resolve():Path('bin/boiled_egg_backend_cli'),
            sdk.resolve().parent/'libboiled_egg.so':Path('lib/libboiled_egg.so')}
    for path in sorted((ROOT/'apps/audition').glob('*.py')):
        copies[path]=Path('apps/audition')/path.name
    for source in copies:
        if not source.is_file():raise FileNotFoundError(source)
    output.mkdir(parents=True)
    for source,target in copies.items():
        dest=output/target;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
    launcher=output/'start-audition.sh'
    launcher.write_text('''#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if test -x .venv/bin/python; then
  exec .venv/bin/python run_audition.py "$@"
else
  exec "${PYTHON:-python3}" run_audition.py "$@"
fi
''',encoding='utf-8');launcher.chmod(0o755)
    files={str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest()
           for p in sorted(output.rglob('*')) if p.is_file()}
    manifest=dict(schema='boiled-egg.audition-linux-package.v1',files=files,
                  builder_python=sys.version.split()[0],builder_platform=platform.platform(),
                  dependencies='Install requirements-audition.txt; system audio/Qt libraries required',
                  hardware_playback_verified=False)
    (output/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--native',type=Path,default=ROOT/'build-transport/libboiled_egg_transport.so')
    p.add_argument('--sdk',type=Path,default=ROOT/'build-sdk/boiled_egg_backend_cli')
    args=p.parse_args();result=package(args.output,args.native,args.sdk)
    print(len(result['files']),'files packaged; external Python/Qt dependencies are not included')
