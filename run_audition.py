#!/usr/bin/env python3
"""Launch the standalone application from a source or Linux binary package."""
from pathlib import Path
import importlib.util
import runpy
import sys

if __name__=='__main__':
    root=Path(__file__).resolve().parent
    missing=[name for name in ('PySide6','numpy','soundfile') if importlib.util.find_spec(name) is None]
    if missing:
        print('Missing dependencies: '+', '.join(missing),file=sys.stderr)
        print('Install: python -m pip install -r requirements-audition.txt',file=sys.stderr)
        raise SystemExit(1)
    sys.path.insert(0,str(root/'apps/audition'))
    runpy.run_path(str(root/'apps/audition/app.py'),run_name='__main__')
