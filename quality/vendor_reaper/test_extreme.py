import copy
import itertools
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import soundfile as sf
import extreme_contract as e
import extreme_study as s

class ExtremeTests(unittest.TestCase):
    def test_separate_range_contract(self):
        for t,p in ((.25,-24),(4,24),(1.5,-5)):
            self.assertGreater(e.Request(t,p).target_frames(96000),0)
        for t,p in ((.125,0),(8,0),(1,36),(True,0),(1,False),(float('nan'),0)):
            with self.assertRaises(ValueError):e.Request(t,p)
        with self.assertRaises(ValueError):s.c.Request(.25,1)
        with self.assertRaises(ValueError):s.c.Request.from_semitones(1,24)

    def test_grid_counts_and_presets(self):
        self.assertEqual([len(s.grid(x)) for x in s.STAGES],[432,432,792])
        self.assertEqual(len(e.PRO),7)
        self.assertEqual([v[1] for v in e.PRO.values()],list(range(1,8)))
        unsupported=sum(e.expected_status(engine,e.Request(T,p))==7 for stage in s.STAGES for _,_,(T,p),engine,_ in s.grid(stage) if engine in e.SDK)
        self.assertEqual(unsupported,276)

    def test_capability_coupling_and_noninteger(self):
        for T,p,result in ((2,12,7),(4,0,7),(1,24,7),(.5,-12,0),(1,7,0),(1.5,-5,0)):
            self.assertEqual(e.expected_status('sdk_harmonic',e.Request(T,p)),result)
            self.assertEqual(e.expected_status('sdk_wsola',e.Request(T,p)),0)

    def test_source_split_and_old_fixtures(self):
        self.assertFalse(set(s.DEVELOP)&set(s.CONFIRM))
        for family in s.DEVELOP+s.BOUNDARY:
            a,meta=s.fixture(family,48000);b,_=s.old.fixture(family,48000)
            np.testing.assert_array_equal(a,b)
        fingerprints=[]
        for family in s.DEVELOP+s.CONFIRM:
            x,_=s.fixture(family,48000);fingerprints.append(s.hashlib.sha256(x.tobytes()).hexdigest())
        self.assertEqual(len(set(fingerprints)),4)

    def test_fractional_harmonic_projection(self):
        _,meta=s.fixture('confirm97',48000);t=np.arange(96000)/48000;k=np.arange(1,31)
        for shift in (-24,7,12,24):
            req=e.Request(1,shift);f=k*97*req.pitch_ratio;keep=f<.45*48000
            amps=.03*s.envelope(f,True)/k**.7
            y=sum(a*np.sin(2*np.pi*v*t+.37*n) for n,v,a in zip(k[keep],f[keep],amps[keep]))
            result=s.measure(y,meta,req)['formant']
            self.assertLess(result['preserved_target_rmse_db'],1e-7)
            self.assertLess(result['unexplained_energy'],1e-15)
            quiet=s.measure(y*.5,meta,req)['formant']
            self.assertAlmostEqual(quiet['preserved_target_rmse_db'],6.020599913,places=6)

    def test_nyquist_exclusions_are_explicit(self):
        _,meta=s.fixture('confirm311',48000);t=np.arange(96000)/48000;k=np.arange(1,31);f=k*311*4
        amps=.03*s.envelope(f,True)/k**.7;keep=f<.45*48000
        y=sum(a*np.sin(2*np.pi*v*t) for v,a in zip(f[keep],amps[keep]))
        result=s.measure(y,meta,e.Request(1,24))['formant']
        self.assertEqual(result['excluded_harmonics'],k[~keep].tolist())
        self.assertLess(result['preserved_target_rmse_db'],1e-7)

    def test_tone_faults_and_silence(self):
        _,meta=s.fixture('low61',48000)
        for T,shift in ((.25,0),(4,0),(1,-24),(1,24),(1.5,-5)):
            req=e.Request(T,shift);t=np.arange(req.target_frames(meta['frames']))/48000
            y=.2*np.sin(2*np.pi*61*req.pitch_ratio*t+.31)
            result=s.measure(y,meta,req)['tone'];self.assertTrue(result['passed'],result)
            wrong=.2*np.sin(2*np.pi*61*req.pitch_ratio*2**(30/1200)*t+.31)
            self.assertFalse(s.measure(wrong,meta,req)['tone']['passed'])
            for bad in (y*0,y[:-1],y*np.nan):
                with self.assertRaises(ValueError):s.measure(bad,meta,req)

    def test_event_clocks_and_gain(self):
        _,meta=s.fixture('bursts',48000)
        for T,shift in ((.25,0),(4,0),(1,-24),(2,12)):
            req=e.Request(T,shift);t=np.arange(req.target_frames(meta['frames']))/48000;p=req.pitch_ratio
            y=sum(.18*np.exp(-.5*((t-a*T)/(.0015/p))**2)*np.cos(2*np.pi*3500*p*(t-a*T)) for a in meta['centers'])
            result=s.event_measure(y,meta,req)
            for ev in result['events']:
                self.assertTrue(ev['passed']);self.assertAlmostEqual(ev['energy_error_db'],0)
            shifted=s.event_measure(np.roll(y,480),meta,req)
            self.assertGreater(abs(shifted['events'][0]['position_ms']),9)
            muted=s.event_measure(y*0,meta,req)
            self.assertTrue(all(v['missing'] and not v['passed'] for v in muted['events']))

    def test_explicit_mode_output_and_receipt_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);src=p/'in.wav';sf.write(src,np.ones(100)*.1,48000,subtype='FLOAT');out=p/'out.wav'
            j=e.job('safe',src,out,48000,100,e.Request(4,24),'pro_low')
            self.assertEqual(j['submode'],3);self.assertEqual(j['output_frames'],400)
            for engine,identifier in (('auto','safe'),('pro_low','bad\nID')):
                with self.assertRaises(ValueError):e.job(identifier,src,out,48000,100,e.Request(),engine)
            out.with_suffix('.rpp').write_text('existing project')
            with self.assertRaises(ValueError):e.job('safe',src,out,48000,100,e.Request(),'pro_low')

    def rows(self,stage='development'):
        rows=[]
        for family,rate,(T,shift),engine,repeat in s.grid(stage):
            r=dict(family=family,rate=rate,time_ratio=T,shift=shift,engine=engine,repeat=repeat,status='failed',error='injected')
            rows.append(r)
        return rows

    def fake_complete(self):
        rows=self.rows()
        for r in rows:
            if r['engine'] in e.SDK and e.expected_status(r['engine'],e.Request(r['time_ratio'],r['shift'])):
                r.update(status='unsupported',capability={'status':7,'expected_status':7})
            else:
                r.update(status='complete',pcm_sha256='a'*64,receipt_sha256='b'*64,
                    metrics=dict(peak=.2,rms=.1,formant=dict(preserved_target_rmse_db=float(list(s.PRESET_ENGINES).index(r['engine'])),off_target_rmse_db=0.,unexplained_energy=0.)))
        return rows

    def test_full_denominator_and_fabricated_unsupported(self):
        rows=self.fake_complete();r=s.assess(rows,'development')
        self.assertEqual((r['rendered'],r['unsupported']),(384,48));self.assertTrue(r['integrity_pass']);self.assertFalse(r['all_requested_rendered'])
        first=rows[0];first.update(status='unsupported',capability={'status':7,'expected_status':7});first.pop('metrics');r=s.assess(rows,'development');self.assertFalse(r['integrity_pass'])
        for bad in ([],rows[:-1],rows+[rows[0]]):
            with self.assertRaises(ValueError):s.assess(bad,'development')

    def test_false_completion_and_repeats(self):
        rows=self.rows()
        for r in rows:r['status']='complete'
        self.assertFalse(s.assess(rows,'development')['integrity_pass'])
        rows=self.fake_complete();rows[0]['pcm_sha256']='c'*64
        self.assertFalse(s.assess(rows,'development')['integrity_pass'])
        rows=self.fake_complete();rows[0]['metrics']['formant']['preserved_target_rmse_db']=float('nan')
        self.assertFalse(s.assess(rows,'development')['integrity_pass'])

    def test_selection_development_only_and_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'lock.json';summary=dict(stage='development',rows=self.fake_complete(),plan_sha256='c'*64)
            sha=s.select(summary,path);self.assertEqual(sha,s.c.fingerprint(path));lock=json.loads(path.read_text())
            self.assertEqual(lock['choices']['-12']['vendor']['engine'],'pro_lowest')
            self.assertEqual(lock['choices']['-12']['sdk']['engine'],'sdk_harmonic')
            self.assertIsNone(lock['choices']['24']['sdk']['engine'])
            with self.assertRaises(ValueError):s.select(summary,path)
            summary['stage']='confirmation'
            with self.assertRaises(ValueError):s.select(summary,Path(tmp)/'invalid.json')

    def test_failed_development_cannot_select(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary=dict(stage='development',rows=self.rows(),plan_sha256='c'*64)
            with self.assertRaises(ValueError):s.select(summary,Path(tmp)/'lock.json')

if __name__=='__main__':unittest.main()
