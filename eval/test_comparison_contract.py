"""Unit tests; generated fixtures are contract checks, not listening evidence."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf
import comparison_contract as c
import run_external as runner


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source.wav'
        sf.write(self.source, np.ones((1000, 2)) * .125, 48000, subtype='FLOAT')
        self.engine = c.Engine('fixture', 'boiled_egg', '/fixture')
        self.probe = dict(config=asdict(self.engine), executable='/fixture', sha256='a'*64, dependencies={})

    def fake_run(self, subtype='FLOAT', count=1000, rate=48000, channels=2, value=.2, exitcode=0, mutate=False):
        def execute(command, **kwargs):
            sf.write(command[2], np.full((count, channels), value), rate, subtype=subtype)
            if mutate:
                sf.write(self.source, np.zeros((1000, 2)), 48000, subtype='FLOAT')
            return subprocess.CompletedProcess(command, exitcode)
        return execute

    def render(self, execute, request=None):
        with patch.object(c, 'identity_unchanged', return_value=True), patch.object(c.subprocess, 'run', side_effect=execute):
            return c.render_case(self.engine, self.probe, self.source, request or c.Request(), self.root/'case')

    def test_request_domains_and_rounding(self):
        for d, p in ((0,1), (1,float('nan')), (float('inf'),1), (.49,1), (1,2.01)):
            with self.assertRaises(ValueError): c.Request(d,p)
        for n in (2,-1,True,1.5):
            with self.assertRaises(ValueError): c.Request(duration_tolerance_frames=n)
        self.assertEqual(c.Request(1.5).target_frames(31),47)
        self.assertEqual(c.Request.from_semitones(1,12).pitch_ratio,2.)
        self.assertEqual(c.Request.from_semitones(1,-12).pitch_ratio,.5)
        for st in (13,float('inf'),float('nan')):
            with self.assertRaises(ValueError): c.Request.from_semitones(1,st)

    def test_tempo_reciprocal_pitch_and_float_not_transcoding(self):
        engine=c.Engine('ff','ffmpeg_rubberband','ffmpeg')
        cmd=engine.command('/ffmpeg',self.source,self.root/'out.wav',c.Request(1.25,2))
        opts=cmd[cmd.index('-af')+1]
        self.assertIn('tempo=0.80000000000000004:pitch=2',opts)
        self.assertIn('channels=together',opts)
        self.assertIn('pitchq=quality',opts)
        self.assertEqual(cmd[cmd.index('-c:a')+1],'pcm_f32le')
        self.assertNotIn('-ar',cmd); self.assertNotIn('-ac',cmd)
        self.assertNotIn('-y',cmd); self.assertIn('-n',cmd)

    def test_preservation_is_explicit_not_policy_substitution(self):
        for kind,policy in [('boiled_egg','harmonic'),('ffmpeg_rubberband','monophonic'),('spectral','preserved')]:
            with self.assertRaises(ValueError):c.Engine('x',kind,'x',formant=policy)
        e=c.Engine('pv','spectral','x',quality='transient',formant='monophonic')
        cmd=e.command('x',self.source,self.root/'out',c.Request(.8,1.5))
        self.assertIn('monophonic',cmd);self.assertIn('--allow-experimental',cmd)
        with self.assertRaises(ValueError):e.command('x',self.source,self.root/'out',c.Request(2,2))

    def test_bad_engine_labels_and_block_rejected(self):
        for name in ('../x','a b','', 'a'*65):
            with self.assertRaises(ValueError):c.Engine(name,'boiled_egg','x')
        with self.assertRaises(ValueError):c.Engine('x','native_zplane','x')
        for block in (0,True,1025):
            with self.assertRaises(ValueError):c.Engine('x','boiled_egg','x',block=block)

    def test_unavailable_engine_does_not_fallback(self):
        with patch.object(c.shutil,'which',return_value=None):
            with self.assertRaises(FileNotFoundError):self.engine.probe()

    def test_valid_float_output_and_raw_peak_not_limited(self):
        receipt=self.render(self.fake_run(value=1.5))
        self.assertEqual(receipt['status'],'passed')
        self.assertEqual(receipt['output']['peak'],1.5)
        c.verify_case(self.root/'case')

    def test_wrong_duration_rejected_without_padding(self):
        receipt=self.render(self.fake_run(count=800), c.Request(1.25))
        self.assertEqual(receipt['status'],'failed')
        self.assertEqual(receipt['duration_error_frames'],-450)
        self.assertEqual(sf.info(self.root/'case/output.wav').frames,800)
        with self.assertRaises(ValueError):c.verify_case(self.root/'case')

    def test_pcm16_output_not_accepted_as_float(self):
        receipt=self.render(self.fake_run(subtype='PCM_16'))
        self.assertIn('output is not float32 WAV',receipt['errors'])
        self.assertEqual(sf.info(self.root/'case/output.wav').subtype,'PCM_16')

    def test_nonfinite_is_rejected_and_file_retained(self):
        receipt=self.render(self.fake_run(value=float('nan')))
        self.assertEqual(receipt['status'],'failed')
        self.assertTrue((self.root/'case/output.wav').exists())

    def test_rate_and_channel_changes_rejected(self):
        receipt=self.render(self.fake_run(rate=44100,channels=1))
        self.assertIn('changed sample_rate',receipt['errors'])
        self.assertIn('changed channels',receipt['errors'])

    def test_timeout_receipt_is_not_success(self):
        def timeout(command,**kwargs):raise subprocess.TimeoutExpired(command,1)
        receipt=self.render(timeout)
        self.assertEqual(receipt['status'],'failed')
        self.assertIn('TimeoutExpired',receipt['errors'][0])
        self.assertTrue((self.root/'case/receipt.json').exists())

    def test_process_failure_with_valid_output_still_fails(self):
        receipt=self.render(self.fake_run(exitcode=7))
        self.assertIn('renderer exit 7',receipt['errors'])
        with self.assertRaises(ValueError):c.verify_case(self.root/'case')

    def test_no_output_does_not_reuse_old_file(self):
        receipt=self.render(lambda command,**kwargs:subprocess.CompletedProcess(command,0))
        self.assertIn('no output created',receipt['errors'])
        with self.assertRaises(FileExistsError):self.render(self.fake_run())

    def test_output_symlink_is_rejected(self):
        def symlink(command,**kwargs):
            Path(command[2]).symlink_to(self.source)
            return subprocess.CompletedProcess(command,0)
        receipt=self.render(symlink)
        self.assertEqual(receipt['status'],'failed')
        self.assertIn('symlink',' '.join(receipt['errors']))

    def test_input_mutation_invalidates_result(self):
        receipt=self.render(self.fake_run(mutate=True))
        self.assertIn('input changed during render',receipt['errors'])

    def test_tampered_output_not_scored(self):
        self.render(self.fake_run())
        sf.write(self.root/'case/output.wav',np.zeros((1000,2)),48000,subtype='FLOAT')
        with self.assertRaisesRegex(ValueError,'changed'):c.verify_case(self.root/'case')

    def test_binary_dependency_mutation(self):
        exe=self.root/'exe';dep=self.root/'library.so'
        exe.write_bytes(b'first');dep.write_bytes(b'first')
        p=dict(executable=str(exe),sha256=c.fingerprint(exe),dependencies={str(dep):c.fingerprint(dep)})
        self.assertTrue(c.identity_unchanged(p))
        dep.write_bytes(b'second');self.assertFalse(c.identity_unchanged(p))

    def test_missing_comparison_never_publishes_listening_manifest(self):
        args=argparse.Namespace(time=1.,pitch=0.,corpus=self.root,limit=1,
              systems=['boiled_egg','ffmpeg_rubberband'],cli=Path('/fixture'),ffmpeg='/fixture',output=self.root/'results')
        def probe(e):return dict(config=asdict(e),executable='/fixture',sha256='a'*64,dependencies={})
        with patch.object(c.Engine,'probe',probe), patch.object(c,'identity_unchanged',return_value=True), \
             patch.object(runner,'identity_unchanged',return_value=True), \
             patch.object(c.subprocess,'run',side_effect=lambda cmd,**kw: subprocess.CompletedProcess(cmd,7) if '-af' in cmd else self.fake_run()(cmd,**kw)):
            # One renderer fails; the whole requested pair must fail closed.
            report=runner.run(args)
        self.assertFalse(report['passed'])
        self.assertEqual(report['actual_cells'],2)
        self.assertFalse((args.output/'render_manifest.csv').exists())
        self.assertTrue((args.output/'summary.json').exists())

    def test_complete_run_and_duplicate_grid_audit(self):
        args=argparse.Namespace(time=1.,pitch=0.,corpus=self.root,limit=1,systems=['boiled_egg'],
              cli=Path('/fixture'),ffmpeg='/fixture',output=self.root/'results')
        def probe(e):return dict(config=asdict(e),executable='/fixture',sha256='a'*64,dependencies={})
        with patch.object(c.Engine,'probe',probe), patch.object(c,'identity_unchanged',return_value=True), \
             patch.object(runner,'identity_unchanged',return_value=True), patch.object(c.subprocess,'run',side_effect=self.fake_run()):
            report=runner.run(args)
        self.assertTrue(report['passed']); self.assertEqual(len(runner.verify_run(args.output)[1]),1)
        path=args.output/'summary.json'
        for rows in ([], report['rows']*2):
            invalid={**report,'rows':rows};path.write_text(json.dumps(invalid))
            with self.assertRaisesRegex(ValueError,'grid'):runner.verify_run(args.output)
        path.write_text(json.dumps(report));(args.output/'plan.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'plan'):runner.verify_run(args.output)

    def test_dominant_frequency_estimator_is_not_target_seeking(self):
        from calibrate_external import pitch_cents
        t=np.arange(96000)/48000
        x=.1*np.sin(2*np.pi*330*t)
        self.assertLess(abs(pitch_cents(x,48000,330)),.01)
        # A deliberately wrong target is not used to select a favorable peak.
        self.assertAlmostEqual(pitch_cents(x,48000,440),1200*np.log2(330/440),places=3)
        before=x.copy();pitch_cents(x,48000,330);np.testing.assert_array_equal(before,x)

if __name__=='__main__':unittest.main()
