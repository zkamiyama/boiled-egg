"""Synthetic test doubles calibrate bookkeeping, never claimed listening evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf
import candidate_evidence as e
import calibrated_listening as l
import comparison_contract as c


class ListeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.panel=[e.Candidate(n,'boiled_egg','/fake/'+n) for n in ('engine_A','engine_B')]
        self.cal=self.root/'calibration';self.raw=self.root/'raw'
        self.source=self.root/'private-source.wav';t=np.arange(96000)/48000
        sf.write(self.source,.125*np.sin(2*np.pi*440*t),48000,subtype='FLOAT')
        def probe(p):return dict(config=e.asdict(p),files={},wrappers={},backend={},software={},alignment_verified=False)
        self.probe=patch.object(e.Candidate,'probe',probe);self.probe.start();self.addCleanup(self.probe.stop)
        self.rend=patch.object(e,'render',self.fake);self.rend.start();self.addCleanup(self.rend.stop)
        e.calibrate(self.panel,self.cal,rates=(48000,),channels=(1,),operations=((.8,0),(1,7)))

    @staticmethod
    def fake(candidate,probe,source,request,case):
        case.mkdir(parents=True);before=c.inspect_audio(source);rate=before['sample_rate'];n=request.target_frames(before['frames'])
        tone=.125*np.sin(2*np.pi*(440*request.pitch_ratio)*np.arange(n)/rate)
        sf.write(case/'output.wav',tone,rate,subtype='FLOAT');after=c.inspect_audio(case/'output.wav')
        receipt=dict(schema=c.SCHEMA,status='passed',errors=[],engine=candidate.name,request=e.asdict(request),
            source=str(source),source_metadata=before,output=after,raw_output_sha256=after['sha256'],candidate_identity=e.digest(probe))
        c.json_write(case/'receipt.json',receipt);return receipt

    def run_raw(self):
        return l.run_panel(self.cal,[self.source],[(.8,0),(1,7)],self.panel,self.raw)

    def rewrite_rows(self,rows):
        c.json_write(self.cal/'rows.json',rows);s=json.loads((self.cal/'summary.json').read_text())
        s.update(rows=len(rows),eligible=sum(r['eligible'] for r in rows),passed=all(r['eligible'] for r in rows),rows_sha256=c.fingerprint(self.cal/'rows.json'))
        c.json_write(self.cal/'summary.json',s)

    def test_explicit_candidate_validation(self):
        for kwargs in ({'formant':'harmonic'},{'kind':'native_elastique'},{'kind':'rubberband_direct','generation':1}):
            args=dict(name='x',kind='boiled_egg',path='x');args.update(kwargs)
            with self.assertRaises(ValueError):e.Candidate(**args)

    def test_exact_operation_and_config_scope(self):
        plan,rows=e.verify_calibration(self.cal);probe=self.panel[0].probe()
        e.require_eligible(plan,rows,probe,48000,1,c.Request(.8))
        for request in (c.Request(.80000001),c.Request(1)):
            with self.assertRaises(ValueError):e.require_eligible(plan,rows,probe,48000,1,request)
        other=e.Candidate('engine_A','boiled_egg','/changed').probe()
        with self.assertRaises(ValueError):e.require_eligible(plan,rows,other,48000,1,c.Request(.8))
        with self.assertRaises(ValueError):e.require_eligible(plan,rows,probe,96000,1,c.Request(.8))

    def test_failed_calibration_is_not_metadata_success(self):
        rows=json.loads((self.cal/'rows.json').read_text());rows[0].update(eligible=False,cents_error=99.,errors=['pitch'])
        self.rewrite_rows(rows)
        e.verify_calibration(self.cal)  # Intact failed evidence is valid evidence, not approval.
        with self.assertRaisesRegex(ValueError,'failed calibration'):self.run_raw()
        self.assertFalse(self.raw.exists())

    def test_missing_duplicate_and_tampered_evidence_rejected(self):
        rows=json.loads((self.cal/'rows.json').read_text())
        for invalid in (rows[:-1],rows+rows[:1]):
            self.rewrite_rows(invalid)
            with self.assertRaisesRegex(ValueError,'grid'):e.verify_calibration(self.cal)
        self.rewrite_rows(rows);(self.cal/'rows.json').write_text('[]')
        with self.assertRaisesRegex(ValueError,'integrity'):e.verify_calibration(self.cal)

    def test_false_eligible_assertion_rejected(self):
        rows=json.loads((self.cal/'rows.json').read_text());rows[0]['cents_error']=50.;self.rewrite_rows(rows)
        with self.assertRaisesRegex(ValueError,'relabeled'):e.verify_calibration(self.cal)

    def test_changed_calibration_audio_rejected(self):
        plan=json.loads((self.cal/'plan.json').read_text());p=self.cal/next(iter(plan['sources'].values()))['path']
        sf.write(p,np.zeros(96000),48000,subtype='FLOAT')
        with self.assertRaisesRegex(ValueError,'input'):e.verify_calibration(self.cal)

    def test_failed_natural_cell_never_becomes_pack(self):
        self.run_raw();s=json.loads((self.raw/'summary.json').read_text());s['passed']=False;c.json_write(self.raw/'summary.json',s)
        with self.assertRaisesRegex(ValueError,'failed'):l.make_pack(self.raw,self.cal,self.root/'pack')
        self.assertFalse((self.root/'pack').exists())

    def test_missing_natural_panel_or_changed_raw_rejected(self):
        self.run_raw();p=self.raw/'summary.json';original=json.loads(p.read_text());broken=dict(original,rows=original['rows'][:-1]);c.json_write(p,broken)
        with self.assertRaisesRegex(ValueError,'panel'):l.verify_panel(self.raw,self.cal)
        c.json_write(p,original);file=self.raw/original['rows'][0]['case']/'output.wav'
        sf.write(file,np.zeros(100),48000,subtype='FLOAT')
        with self.assertRaises(ValueError):l.verify_panel(self.raw,self.cal)

    def test_listener_anonymity_no_default_ratings_and_separate_key(self):
        self.run_raw();out=self.root/'pack';report=l.make_pack(self.raw,self.cal,out)
        self.assertEqual((report['trials'],report['choices'],report['ratings_received']),(2,4,0))
        for p in (out/'listener').glob('*'):
            if p.is_file():
                text=p.read_text();self.assertNotIn('engine_A',text);self.assertNotIn('engine_B',text);self.assertNotIn('private-source',text)
        page=(out/'listener/index.html').read_text();self.assertIn('未回答',page)
        self.assertFalse((out/'listener/key.json').exists())
        self.assertEqual(l.validate_answers(out,dict(pack_id=report['pack_id'],ratings=[])),[])
        trials=json.loads((out/'listener/trials.json').read_text())['trials']
        answer=dict(trial=trials[0]['trial'],choice='A',dimension='naturalness',rating=4)
        self.assertEqual(l.validate_answers(out,dict(pack_id=report['pack_id'],ratings=[answer])),[answer])
        for wrong in ([answer,answer],[dict(answer,rating=float('nan'))],[dict(answer,choice='Z')],[dict(answer,rating=True)]):
            with self.assertRaises(ValueError):l.validate_answers(out,dict(pack_id=report['pack_id'],ratings=wrong))

    def test_common_gain_and_raw_unchanged(self):
        self.run_raw();before={str(p):c.fingerprint(p) for p in self.raw.rglob('output.wav')}
        out=self.root/'pack';l.make_pack(self.raw,self.cal,out)
        keys=json.loads((out/'organizer/key.json').read_text())['choices']
        for trial in {k['trial'] for k in keys}:self.assertEqual(len({k['common_gain'] for k in keys if k['trial']==trial}),1)
        for p,h in before.items():self.assertEqual(c.fingerprint(Path(p)),h)
        for p in (out/'listener/audio').glob('*.wav'):self.assertLessEqual(c.inspect_audio(p)['peak'],.9500001)

    def test_no_destructive_reuse_and_escape(self):
        self.run_raw();out=self.root/'pack';out.mkdir();(out/'keep').write_text('important')
        with self.assertRaises(ValueError):l.make_pack(self.raw,self.cal,out)
        self.assertEqual((out/'keep').read_text(),'important')
        with self.assertRaises(ValueError):e.inside(self.cal,'../private-source.wav')
        with self.assertRaises(FileExistsError):self.run_raw()

    def test_aslr_probe_log_is_not_execution_identity(self):
        original=e.Candidate.probe
        def changed_log(candidate):
            probe=original(candidate);probe['backend']={'dependency_probe':'libc (0x12345678)'}
            return probe
        with patch.object(e.Candidate,'probe',changed_log):
            self.assertTrue(self.run_raw()['passed'])
        plan=json.loads((self.raw/'plan.json').read_text())
        self.assertIn('0x12345678',plan['observed_probes']['engine_A']['backend']['dependency_probe'])
        l.verify_panel(self.raw,self.cal)

    def test_changed_resolved_dependency_is_not_authorized(self):
        original=e.Candidate.probe
        def changed(candidate):
            probe=original(candidate);probe['files']={'different.so':'a'*64};return probe
        with patch.object(e.Candidate,'probe',changed):
            with self.assertRaisesRegex(ValueError,'execution identity'):self.run_raw()
        self.assertFalse(self.raw.exists())

    def test_unknown_operation_never_renders(self):
        with self.assertRaises(ValueError):l.run_panel(self.cal,[self.source],[(1,3)],self.panel,self.raw)
        self.assertFalse(self.raw.exists())

if __name__=='__main__':unittest.main()
