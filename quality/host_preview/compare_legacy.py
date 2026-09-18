"""Exact legacy CLAP behavior, not a perceptual score. No candidate imports."""
import argparse,csv,hashlib,itertools,json
from pathlib import Path
KEYS=('rate','block','pitch','scenario')
VALUES=('frames','latency','tail','last_pitch','audio_hash')

def read(path):
    rows={}
    with Path(path).open(newline='') as f:
        r=csv.DictReader(f)
        if r.fieldnames!=list(KEYS+VALUES):raise ValueError('columns')
        for row in r:
            if None in row or any(v is None for v in row.values()):raise ValueError('ragged')
            key=tuple(int(row[k]) for k in KEYS);value=tuple(int(row[k]) for k in VALUES)
            if key in rows or value[0]<=0 or not 0<=value[-1]<2**64:raise ValueError('duplicate or invalid')
            rows[key]=value
    expected=set(itertools.product((44100,48000,88200,96000),(32,257),(-12,0,12),(0,1)))
    if set(rows)!=expected:raise ValueError('incomplete or unexpected grid')
    return rows

def compare(original,candidate):
    a,b=read(original),read(candidate)
    differences=[k for k in a if a[k]!=b[k]]
    if differences:raise ValueError('legacy output/contract changed: '+str(differences))
    for key in a:
        if key[1]==32 and a[key]!=a[(key[0],257,*key[2:])]:raise ValueError('partition changed')
    return {'cases':len(a),'partition_pairs':len(a)//2,'exact':True}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('original',type=Path);p.add_argument('candidate',type=Path);p.add_argument('--output',type=Path)
    args=p.parse_args();result=compare(args.original,args.candidate)
    result['files']={str(q):hashlib.sha256(q.read_bytes()).hexdigest() for q in (args.original,args.candidate)}
    text=json.dumps(result,indent=2)+'\n'
    if args.output:
        if args.output.exists():raise ValueError('new output required')
        args.output.write_text(text)
    print(text)
