"""Synthetic checkpoint recovery tests; fixture amplitudes are not quality results."""
import copy,json,sys,unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_fuzzy_batches as b
import test_fuzzy_corpus as fixture

class SerialPool:
    def __init__(self,**kwargs):pass
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def map(self,fn,jobs):return map(fn,jobs)

class BatchTests(unittest.TestCase):
    setUp=fixture.FuzzyCorpusTests.setUp
    save=fixture.FuzzyCorpusTests.save
    def args(self):
        return fixture.argparse.Namespace(ref_dir=self.refs,test_dir=self.tests,catalog=self.catalog,
            pv_cli=Path(sys.executable),multires_cli=Path(sys.executable),source_commit='a'*40,
            formants=['harmonic'],block=64,workers=1,output=self.root/'result',resume=False,batch_limit=2)
    def fake_job(self,args):
        c,refs,tests,pv,multi,output,formants,block=args
        folder=output/'renders'/c['condition_id'];folder.mkdir(parents=True)
        pairs=[(p,f) for p in b.e.PROFILES for f in formants]
        if c['family']=='derived':pairs.append((b.e.BASELINE,'not_applicable'))
        rows=[]
        for p,f in pairs:
            path=folder/(b.e.BASELINE+'.wav' if p==b.e.BASELINE else p+'_'+f+'.wav')
            fixture.sf.write(path,self.x,48000,subtype='FLOAT')
            rows.append(dict(**c,profile=p,formant=f,env=.5,onset=.8,peak=.2,rms=.1,duration_error_frames=0,
                render_path=path.relative_to(output).as_posix(),render_sha256=b.e.fingerprint(path)))
        return rows
    def execute(self,a):
        with mock.patch.object(b.cf,'ProcessPoolExecutor',SerialPool),mock.patch.object(b.e,'job',side_effect=self.fake_job) as job:
            result=b.run(a)
            return result,job.call_count
    def test_partial_then_resume_only_missing(self):
        a=self.args();r,n=self.execute(a);self.assertFalse(r['complete']);self.assertEqual(n,2)
        self.assertFalse(a.output.exists())
        a.resume=True;a.batch_limit=0;r,n=self.execute(a)
        self.assertTrue(r['complete']);self.assertEqual(n,5);self.assertEqual(r['measurements'],36)
        self.assertEqual(r['listening_status'],'not_listened')
    def test_resume_requires_explicit_flag(self):
        a=self.args();self.execute(a)
        with self.assertRaisesRegex(ValueError,'resume'):self.execute(a)
    def test_changed_config_rejected_without_overwriting(self):
        a=self.args();self.execute(a);a.resume=True;a.block=32
        with self.assertRaisesRegex(ValueError,'identity'):self.execute(a)
    def test_corrupt_completed_audio_regenerated_and_recorded(self):
        a=self.args();self.execute(a);stage=a.output.with_name('result.incomplete')
        next((stage/'renders').rglob('*.wav')).write_bytes(b'corrupt')
        a.resume=True;a.batch_limit=0;r,n=self.execute(a)
        self.assertTrue(r['complete']);self.assertEqual(n,6)
        self.assertIn('checkpoint render path/hash mismatch',(a.output/'attempts.jsonl').read_text())
    def test_changed_input_rejected(self):
        a=self.args();self.execute(a);a.resume=True
        fixture.sf.write(self.refs/'A.wav',self.x*.5,48000,subtype='FLOAT')
        with self.assertRaisesRegex(ValueError,'identity'):self.execute(a)
    def test_failed_cell_retained_as_incomplete(self):
        a=self.args()
        with mock.patch.object(b.cf,'ProcessPoolExecutor',SerialPool),mock.patch.object(b.e,'job',side_effect=RuntimeError('injected failure')):
            with self.assertRaises(RuntimeError):b.run(a)
        self.assertFalse(a.output.exists())
        self.assertTrue((a.output.with_name('result.incomplete')/'INCOMPLETE.json').exists())
        a.resume=True;a.batch_limit=0;r,_=self.execute(a);self.assertTrue(r['complete'])
    def test_final_output_refuses_overwrite(self):
        a=self.args();a.batch_limit=0;self.execute(a)
        with self.assertRaisesRegex(ValueError,'final output'):self.execute(a)

if __name__=='__main__':unittest.main()
