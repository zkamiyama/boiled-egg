#!/usr/bin/env python3
"""Refuse any standalone-app integration that alters protected main components."""
import argparse
import hashlib
import json
from pathlib import Path

PROTECTED=('src','include','adapters','cmake','eval','research','CMakeLists.txt')

def index(root):
    root=Path(root);result={}
    for prefix in PROTECTED:
        path=root/prefix
        # Some main versions have no research directory; its absence is also bound.
        result[prefix+'/__present__']=path.exists()
        for file in sorted(path.rglob('*')) if path.is_dir() else ([path] if path.is_file() else []):
            if file.is_symlink(): raise ValueError('Protected source symlink')
            if file.is_file():result[str(file.relative_to(root))]=hashlib.sha256(file.read_bytes()).hexdigest()
    return result

def audit(reference, candidate):
    a,b=index(reference),index(candidate)
    if not a.get('src/__present__') or not a.get('include/__present__'):
        raise ValueError('Missing main reference source')
    if a!=b: raise ValueError('Protected main source or build configuration changed')
    return dict(schema='boiled-egg.audition-scope.v1',unchanged=True,
                file_count=sum(type(v) is str for v in a.values()),protected=a)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('reference','candidate','output'):parser.add_argument('--'+arg,type=Path,required=True)
    args=parser.parse_args();result=audit(args.reference,args.candidate)
    with args.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(result['file_count'],'protected main files unchanged')
