"""Real C++ freeze comparison, exact saved output and failure/cancel controls."""
from pathlib import Path
import json
import tempfile
import threading
import unittest
import numpy as np
import soundfile as sf
import native_batch as b
from native import Transport
from comparison_batch import save_result


def audio():
    t = np.arange(24000)/48000
    x = (.1*np.cos(2*np.pi*223*t)).astype('float32')
    return np.c_[x, -.375*x]


class NativeBatchTests(unittest.TestCase):
    def test_six_fresh_native_freezes_from_same_loaded_anchor(self):
        with tempfile.TemporaryDirectory() as d:
            source=audio();before=source.copy();root=Path(d)/'freeze';notices=[]
            report=b.render_batch(source,48000,root,12000.,.2,0,7,progress=notices.append)
            self.assertTrue(report['all_passed']);self.assertEqual(len(report['results']),6)
            self.assertEqual(len(notices),6);self.assertEqual(notices[-1]['completed'],6)
            np.testing.assert_array_equal(source,before)
            for row in report['results']:
                receipt=row['receipt'];y,rate=sf.read(root/row['output'],dtype='float32',always_2d=True)
                self.assertEqual(y.shape,(9600,2));self.assertEqual(rate,48000)
                self.assertEqual(receipt['final_source_position'],12000.)
                self.assertGreater(receipt['synthesis_frames'],1)
                self.assertGreater(float(np.max(np.abs(y))),.01)
                self.assertEqual(receipt['output_sha256'],b._sha(root/row['output']))
                # Independent direct call, different block partition; not one shared output loop.
                with Transport(source,48000,row['index']) as h:
                    h.set(0,7);h.seek(12000.)
                    expected=np.concatenate([h.render(min(257,9600-i)) for i in range(0,9600,257)])
                np.testing.assert_array_equal(y,expected)
            save_result(root/report['results'][0]['output'],Path(d)/'selected.wav')
            self.assertTrue((Path(d)/'selected.wav.json').is_file())
            self.assertEqual(json.loads((root/'comparison.json').read_text())['output_frames'],9600)

    def test_positive_speed_unequal_rates_and_unavailable_formants_are_distinct(self):
        with tempfile.TemporaryDirectory() as d:
            report=b.render_batch(audio(),48000,Path(d)/'result',1000.,.1,4,0,1,0,44100)
            self.assertEqual([r['status'] for r in report['results']],['passed']*3+['unsupported']*3)
            self.assertFalse(report['all_passed'])
            for row in report['results'][:3]:
                self.assertAlmostEqual(row['receipt']['final_source_position'],20200.,places=7)
            self.assertEqual(len(list((Path(d)/'result').glob('*.wav'))),3)

    def test_cancel_removes_partial_output_and_records_all_modes(self):
        class CancelDuringRender:
            def __init__(self): self.calls=0
            def is_set(self):
                self.calls+=1
                return self.calls>=4
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'cancel'
            r=b.render_batch(audio(),48000,root,12000.,.2,cancel=CancelDuringRender())
            self.assertEqual([row['status'] for row in r['results']],['cancelled']*6)
            self.assertFalse(list(root.glob('*.wav')))
            self.assertFalse(list(root.glob('*.wav.json')))
            self.assertTrue((root/'comparison.json').is_file())

    def test_reject_invalid_inputs_and_missing_library_without_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'bad'
            for kw in ({'speed':float('nan')},{'seconds':float('inf')},
                       {'speed':-1},{'policy':0,'formant':1},{'position':-1},
                       {'output_rate':32000},{'library':str(Path(d)/'missing.so')}):
                args=dict(position=1000.,seconds=.1);args.update(kw)
                with self.assertRaises((ValueError,FileNotFoundError)):
                    b.render_batch(audio(),48000,root,**args)
                self.assertFalse(root.exists())
            root.mkdir();sentinel=root/'keep';sentinel.write_text('unchanged')
            with self.assertRaises(FileExistsError):b.render_batch(audio(),48000,root,1000.,.1)
            self.assertEqual(sentinel.read_text(),'unchanged')

if __name__=='__main__':unittest.main()
