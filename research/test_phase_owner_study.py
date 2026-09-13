"""Grid, journal and command-routing checks; fixtures are not quality evidence."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import soundfile as sf
import eval_phase_owner_study as e

class SerialPool:
    def __init__(self,*a,**k):pass
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def map(self,fn,jobs):return map(fn,jobs)

class StudyTest(unittest.TestCase):
    def test_grid_rejects_duplicate_missing_extra_and_nonfinite(self):
        rows=[dict(id=i,value=float(i)) for i in range(3)]
        expected={(i,) for i in range(3)}
        e.validate_rows(rows,expected,('id',))
        for bad in (rows[:-1],rows+rows[:1],rows+[dict(id=3,value=3.)],
                    [*rows[:-1],dict(id=2,value=float('nan'))]):
            with self.assertRaises(ValueError):e.validate_rows(bad,expected,('id',))
    def test_resume_reuses_only_exact_configuration(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(e.cf,'ProcessPoolExecutor',SerialPool):
            cache=Path(tmp)/'cache';manifest={'variant':'fixed','input':'sha'}
            calls=[]
            def calc(i):calls.append(i);return [dict(id=i,value=2.*i)]
            first=e.cached_run(cache,manifest,calc,[0,1,2],1)
            self.assertEqual(calls,[0,1,2]);calls.clear()
            self.assertEqual(e.cached_run(cache,manifest,calc,[0,1,2],1),first)
            self.assertFalse(calls)
            with self.assertRaisesRegex(ValueError,'identity'):e.cached_run(cache,{'variant':'changed'},calc,[0,1,2],1)
            p=cache/'cell-0001.json';value=json.loads(p.read_text());value['rows'][0]['value']=999.;p.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'integrity'):e.cached_run(cache,manifest,calc,[0,1,2],1)
    def test_partial_resume_and_unbound_cache(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(e.cf,'ProcessPoolExecutor',SerialPool):
            cache=Path(tmp);(cache/'junk').write_text('x')
            with self.assertRaisesRegex(ValueError,'unbound'):e.cached_run(cache,{},lambda x:[],[],1)
            (cache/'junk').unlink()
            def fail(i):
                if i==1:raise RuntimeError('interrupted')
                return [dict(id=i)]
            with self.assertRaisesRegex(RuntimeError,'interrupted'):e.cached_run(cache,{},fail,[0,1],1)
            calls=[]
            def resume(i):calls.append(i);return [dict(id=i)]
            self.assertEqual(e.cached_run(cache,{},resume,[0,1],1),[dict(id=0),dict(id=1)])
            self.assertEqual(calls,[1])
    def test_render_routing_and_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'result.wav';sf.write(path,np.ones(100),48000,subtype='FLOAT')
            for operation in ('pitch','time_stretch'):
                with patch.object(e.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'','')) as proc:
                    e.render(Path(tmp),path,path,1.5,48000,'off',operation)
                    cmd=proc.call_args.args[0]
                    self.assertEqual('--execution' in cmd,operation=='pitch')
                    self.assertEqual(cmd[cmd.index('--time')+1],'1.5' if operation=='time_stretch' else '1')
            with patch.object(e.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','fixture failure')):
                with self.assertRaisesRegex(RuntimeError,'fixture failure'):e.render(Path(tmp),path,path,1,48000,'off')
    def test_wrong_rate_is_not_scored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'result.wav';sf.write(path,np.ones(100),44100,subtype='FLOAT')
            with patch.object(e.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'','')):
                with self.assertRaisesRegex(ValueError,'sample rate'):e.render(Path(tmp),path,path,1,48000,'off')

if __name__=='__main__':unittest.main()
