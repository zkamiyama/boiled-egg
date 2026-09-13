"""Opt-in feature controls: calibration, CLI contracts and direct DSP integration."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import numpy as np
import soundfile as sf
sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_research_features as e
from check_fuzzy_quality import analyze


class FeatureToolsTest(unittest.TestCase):
    def test_candidate_scales_once_and_is_explicit(self):
        cmd=e.command(Path('/build'),Path('in.wav'),Path('out.wav'),'fuzzy','harmonic',1.5,96000,'candidate',.75)
        self.assertEqual(cmd[cmd.index('--fft')+1],'1024')
        self.assertEqual(cmd[cmd.index('--rate-policy')+1],'scaled')
        self.assertEqual(cmd[cmd.index('--timing')+1],'centered')
        self.assertEqual(cmd[cmd.index('--formant-ratio')+1],'0.75')

    def test_legacy_preserves_previous_comparison_configuration(self):
        cmd=e.command(Path('/build'),Path('in'),Path('out'),'general','harmonic',1.5,96000,'legacy')
        self.assertEqual(cmd[cmd.index('--fft')+1],'4096')
        self.assertEqual(cmd[cmd.index('--hop')+1],'512')
        self.assertNotIn('--rate-policy',cmd);self.assertNotIn('--timing',cmd)
        multi=e.command(Path('/build'),Path('in'),Path('out'),'multires','harmonic',1.5,96000,'timing')
        self.assertNotIn('--fft',multi);self.assertNotIn('--rate-policy',multi)

    def test_bad_variant_rejected(self):
        with self.assertRaises(ValueError):e.command(Path('/b'),Path('in'),Path('out'),'fuzzy','off',1,48000,'auto')

    def test_attack_fixture_has_eight_distinct_hop_phases(self):
        for rate in (48000,96000):
            x,meta=e.attack_fixture(rate,1.)
            positions=[round(s*rate) for s in meta['starts']]
            self.assertEqual(len({n%(256*(rate//48000)) for n in positions}),8)
            self.assertEqual(x.shape,(2*rate,1))
            self.assertTrue(np.isfinite(x).all())
            self.assertEqual(e.m.attacks(x,rate,meta['starts'],meta['duration'])['pre_energy_pct'],0)

    def test_formant_oracle_moves_envelope_not_partial_frequencies(self):
        a,ma=e.formant_fixture('vowel_a',48000,1.,.5)
        b,mb=e.formant_fixture('vowel_a',48000,1.,2.)
        np.testing.assert_array_equal(ma['frequencies'],mb['frequencies'])
        self.assertFalse(np.array_equal(a,b))
        self.assertAlmostEqual(float(np.mean(a*a)),.01,places=7)

    def test_render_checks_metadata_and_failures(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'out.wav';sf.write(path,np.ones(100),44100,subtype='FLOAT')
            with mock.patch.object(e.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'','')):
                with self.assertRaises(ValueError):e.render([],path,(100,1),48000)
                with self.assertRaises(ValueError):e.render([],path,(99,1),44100)
            with mock.patch.object(e.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','failed')):
                with self.assertRaisesRegex(RuntimeError,'failed'):e.render([],path,(100,1),44100)


@unittest.skipUnless(os.environ.get('BOILED_EGG_PV_CLI') and os.environ.get('BOILED_EGG_MULTIRES_CLI'),
                     'explicit real CLI paths required')
class FeatureIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.pv=Path(os.environ['BOILED_EGG_PV_CLI']);self.multi=Path(os.environ['BOILED_EGG_MULTIRES_CLI'])
        self.src=self.root/'input.wav';self.dst=self.root/'output.wav'

    def cmd(self,profile,rate,pitch,variant,formant='off',ratio=1):
        cmd=e.command(self.pv.parent,self.src,self.dst,profile,formant,pitch,rate,variant,ratio)
        cmd[0]=str(self.multi if profile=='multires' else self.pv)
        return cmd

    def test_centered_attack_timing_48_and96k(self):
        for rate in (48000,96000):
            source,meta=e.attack_fixture(rate,1.);sf.write(self.src,source,rate,subtype='FLOAT')
            for profile in ('transient','fuzzy','multires'):
                for pitch in (.5,2.):
                    x,_=e.render(self.cmd(profile,rate,pitch,'candidate'),self.dst,source.shape,rate)
                    measured=e.m.attacks(x,rate,meta['starts'],meta['duration'])
                    self.assertLess(abs(measured['centroid_bias_ms']),.2,(rate,profile,pitch,measured))

    def test_new_cli_flags_reject_invalid_controls(self):
        sf.write(self.src,np.ones(1000)*.1,48000,subtype='FLOAT')
        for cli in (self.pv,self.multi):
            for args in (['--timing','auto'],['--rate-policy','auto'],['--formant-ratio','nan'],
                         ['--formant-ratio','0.49'],['--formant-ratio','2.01'],['--formant-ratio','1junk'],
                         ['--formant-semitones','inf'],['--formant-ratio']):
                p=subprocess.run([str(cli),str(self.src),str(self.dst),'--time','1','--formant','harmonic',*args],capture_output=True)
                self.assertNotEqual(p.returncode,0,args);self.assertFalse(self.dst.exists())
            p=subprocess.run([str(cli),str(self.src),str(self.dst),'--time','1','--formant','off','--formant-ratio','.75'],capture_output=True)
            self.assertNotEqual(p.returncode,0);self.assertFalse(self.dst.exists())

    def test_formant_semitone_alias_is_byte_identical(self):
        source,_=e.formant_fixture('vowel_i',48000,1,1);sf.write(self.src,source,48000,subtype='FLOAT')
        for profile in ('general','fuzzy','multires'):
            for st,ratio in [(-12,.5),(12,2.)]:
                cmd=self.cmd(profile,48000,1,'candidate','harmonic',ratio)
                e.render(cmd,self.dst,source.shape,48000);original=self.dst.read_bytes()
                j=cmd.index('--formant-ratio');cmd[j:j+2]=['--formant-semitones',str(st)]
                e.render(cmd,self.dst,source.shape,48000)
                self.assertEqual(self.dst.read_bytes(),original)

    def test_independent_formant_control_preserves_pitch_frequency(self):
        rate=48000;t=np.arange(rate*2)/rate
        source=(.2*np.sin(2*np.pi*440*t)).astype('float32')[:,None];sf.write(self.src,source,rate,subtype='FLOAT')
        for profile in ('general','transient','fuzzy','multires'):
            for ratio in (.5,2.):
                x,_=e.render(self.cmd(profile,rate,1.5,'candidate','harmonic',ratio),self.dst,source.shape,rate)
                cents,_=analyze(x,rate,660.)
                self.assertLess(abs(cents),3,(profile,ratio,cents))

if __name__=='__main__':unittest.main()
