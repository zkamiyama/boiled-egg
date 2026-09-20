"""Integrity/calibration controls, not a claim that all research cells sound good."""
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import numpy as np
import soundfile as sf
import comparison_contract as c
import offline_pv_benchmark as m
import wsola_offline as h
import wsola_low_tone_study as s


class Calibration(unittest.TestCase):
    def test_frequency_oracles_and_wrong_pitch(self):
        errors = []
        for rate in h.RATES:
            t = np.arange(round(.45*rate))/rate
            for f in (41, 61, 83, 223):
                for shift in s.SHIFTS:
                    target = f*2**(shift/12)
                    for phase in (0, np.pi/3):
                        y = .2*np.sin(2*np.pi*target*t+phase)
                        errors.append(abs(m.tone_error(y, rate, target)))
                    wrong = .2*np.sin(2*np.pi*target*2**(50/1200)*t)
                    self.assertGreater(abs(m.tone_error(wrong, rate, target)), 49)
        self.assertLess(max(errors), .1)

    def test_position_and_unwanted_components(self):
        x, meta = s.fixture('bursts', 48000)
        delayed = np.concatenate((np.zeros(480), x[:-480]))
        for a, b in zip(m.events(x, 48000, meta['centers']), m.events(delayed, 48000, meta['centers'])):
            self.assertAlmostEqual(b['position_error_ms']-a['position_error_ms'], 10, places=5)
        t = np.arange(48000)/48000
        y = .2*np.sin(2*np.pi*61*t)+.1*np.sin(2*np.pi*173*t)
        _, residual = m.components(y, 48000, [61])
        self.assertAlmostEqual(residual, .2, places=10)
        for y in (np.zeros(100), np.full(100, np.nan)):
            with self.assertRaises(ValueError): m.tone_error(y, 48000, 61)

    def test_fixed_configuration(self):
        self.assertEqual(h.configuration(48000, 32, 'default', 12), (1024, 128))
        self.assertEqual(h.configuration(96000, 64, 'long_wide', 12), (8192, 1920))
        for rate in h.RATES:
            for profile in h.PROFILES:
                window, search = h.configuration(rate, 64, profile, 12)
                self.assertLess(search, window//2)
                self.assertLessEqual(search, window/4)
        for args in ((44100, 64, 'default', 0), (48000, 64, 'auto', 0), (48000, 64, 'default', float('nan')), (48000, 64, 'default', 13)):
            with self.assertRaises(ValueError): h.configuration(*args)

    def test_no_silent_or_malformed_input(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'x.wav'; x, _ = s.fixture('tone61_phase0', 48000)
            sf.write(p, x, 48000, subtype='FLOAT'); raw = p.read_bytes()
            got, rate = h.read_input(p); np.testing.assert_array_equal(x, got); self.assertEqual(rate, 48000)
            data_offset = raw.index(b'data')
            bad_size = bytearray(raw); struct.pack_into('<I', bad_size, data_offset+4, 0x7ffffffe)
            bad_riff = bytearray(raw); struct.pack_into('<I', bad_riff, 4, 0)
            for value in (raw[:-16], bad_size, bad_riff, b'notawav'):
                p.write_bytes(value)
                with self.assertRaises(ValueError): h.read_input(p)
            for value, rate in ((np.zeros(100), 48000), (np.full(100, np.nan), 48000), (np.ones((100,2))*.1,48000), (x,44100)):
                sf.write(p, value, rate, subtype='FLOAT')
                with self.assertRaises(ValueError): h.read_input(p)

    def test_grid_rejects_subsets_duplicates(self):
        rows = [dict(zip(('name','rate','block','shift','profile','repeat'), values), status='failed')
                for values in __import__('itertools').product(s.FAMILIES,h.RATES,s.BLOCKS,s.SHIFTS,h.PROFILES,range(3))]
        self.assertEqual(len(rows), 1440); s.validate_grid(rows)
        self.assertFalse(s.assess(rows)['execution_complete'])
        for bad in (rows[:-1], rows+[rows[0]], []):
            with self.assertRaises(ValueError): s.validate_grid(bad)

    def test_transient_stops_not_average_cancellation(self):
        rows = []
        for values in __import__('itertools').product(s.FAMILIES,h.RATES,s.BLOCKS,s.SHIFTS,h.PROFILES,range(3)):
            r = dict(zip(('name','rate','block','shift','profile','repeat'),values))
            r.update(status='complete', pcm_sha256='identical', audio={'sha256':'container'+str(r['repeat'])}, native={'host_render_seconds':.1},
                     metrics=dict(pitch_error_cents=0, amplitude_error_db=[0], undesired_energy_fraction=0,
                                  events=[dict(position_error_ms=0,width_ms=4)]))
            if r['name']=='bursts' and r['profile']=='long_wide' and r['shift']==-12:
                r['metrics']['events'][0]['width_ms']=8
            rows.append(r)
        result=s.assess(rows)
        self.assertEqual(len(result['long_wide_transient_stops']),4)
        self.assertTrue(result['repeat_pcm_identical'])
        self.assertFalse(result['repeat_wav_identical'])
        self.assertIsNone(result['quality_selection'])
        self.assertEqual(result['decision'],'research_only_no_product_promotion')

    def test_pcm_hash_not_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'x.wav'; x,_=s.fixture('tone61_phase0',48000)
            sf.write(p,x,48000,subtype='FLOAT'); before=s.pcm_hash(p); original=c.fingerprint(p)
            raw=bytearray(p.read_bytes()); peak=raw.index(b'PEAK')
            timestamp=struct.unpack_from('<I',raw,peak+12)[0]
            struct.pack_into('<I',raw,peak+12,timestamp+1); p.write_bytes(raw)
            self.assertNotEqual(original,c.fingerprint(p));self.assertEqual(before,s.pcm_hash(p))
            x[100]+=.01;sf.write(p,x,48000,subtype='FLOAT')
            self.assertNotEqual(before,s.pcm_hash(p))


class NativeControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Missing required binaries are errors, not skips or fake native mocks.
        cls.library=Path(os.environ['BOILED_EGG_WSOLA_LIBRARY']).resolve(strict=True)
        cls.cli=Path(os.environ['BOILED_EGG_CLI_BACKEND']).resolve(strict=True)
        cls.sha=c.fingerprint(cls.library); cls.native=h.Native(cls.library,cls.sha)

    def test_identity_length_and_reset(self):
        for rate in h.RATES:
            x,_=s.fixture('tone223_phase0',rate)
            for profile in h.PROFILES:
                y,_=self.native.render(x,rate,0,profile,64,reset_check=True)
                self.assertLessEqual(float(np.max(np.abs(x-y))), 2*np.finfo(np.float32).eps*float(np.max(np.abs(x))))

    def test_partitions_and_recreation(self):
        x,_=s.fixture('harmonic83',48000)
        for profile in h.PROFILES:
            outputs=[self.native.render(x,48000,12,profile,b)[0] for b in (32,64,1024)]
            for y in outputs[1:]: np.testing.assert_array_equal(outputs[0],y)

    def test_actual_default_cli_pcm(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for rate in h.RATES:
                x,_=s.fixture('tone61_phase0',rate); src=root/f'in{rate}.wav';sf.write(src,x,rate,subtype='FLOAT')
                for shift in s.SHIFTS:
                    out=root/f'out{rate}-{shift}.wav'
                    subprocess.run([str(self.cli),str(src),str(out),'--backend','wsola','--quality','general','--pitch-semitones',str(shift),'--block','64'],check=True,capture_output=True,timeout=20)
                    control,_=sf.read(out,dtype='float32'); y,_=self.native.render(x,rate,shift,'default',64)
                    np.testing.assert_array_equal(control,y)

    def test_cli_receipts_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);p=root/'x.wav';x,_=s.fixture('tone223_phase0',48000);sf.write(p,x,48000,subtype='FLOAT')
            command=[sys.executable,str(Path(h.__file__)),str(p),str(root/'ok'),'--library',str(self.library),
                     '--library-sha256',self.sha,'--execution','offline','--allow-experimental','--profile','long_wide']
            r=subprocess.run(command,capture_output=True,timeout=20); self.assertEqual(r.returncode,0,r.stderr)
            report=json.loads((root/'ok/report.json').read_text());self.assertEqual(report['status'],'complete')
            original=c.fingerprint(root/'ok/output.wav')
            r=subprocess.run(command,capture_output=True,timeout=20);self.assertEqual(r.returncode,2)
            self.assertEqual(original,c.fingerprint(root/'ok/output.wav'))
            for i,change in enumerate(('hash','optin','pitch','zero')):
                cmd=command.copy();out=root/f'bad{i}';cmd[3]=str(out)
                if change=='hash':cmd[cmd.index('--library-sha256')+1]='0'*64
                if change=='optin':cmd.remove('--allow-experimental')
                if change=='pitch':cmd+=['--pitch-semitones','13']
                if change=='zero':sf.write(p,np.zeros(100),48000,subtype='FLOAT')
                r=subprocess.run(cmd,capture_output=True,timeout=20);self.assertEqual(r.returncode,2,r.stderr)
                self.assertFalse((out/'output.wav').exists());self.assertEqual(json.loads((out/'report.json').read_text())['status'],'blocked')


if __name__=='__main__':unittest.main()
