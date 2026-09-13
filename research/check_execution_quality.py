#!/usr/bin/env python3
"""Run the existing 270-case gate through the scheduled SIMD CLI path."""
import argparse,json
from pathlib import Path
from unittest.mock import patch
import check_feature_quality as q

def run(build,output):
    original=q.e.command
    def command(*args,**kwargs):return original(*args,**kwargs)+['--execution','scheduled','--simd','on']
    with patch.object(q.e,'command',command):result=q.run(build,output)
    result['execution']='scheduled';result['simd']='on';result['thresholds_changed']=False
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=run(a.build,a.output);print(len(r['rows']),'cases;',len(r['failed']),'failures');raise SystemExit(bool(r['failed']))
