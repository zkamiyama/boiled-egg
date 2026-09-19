"""Independent source-clock, hold/resume and invalid-batch history checks."""
import unittest
import numpy as np
from native import Transport


def render(h, total, block=257):
    return np.concatenate([h.render(min(block, total-i)) for i in range(0, total, block)])


def crossing_frequency(x, rate):
    # Linear zero-crossing times: independent of the FFT peak-based assessor.
    index = np.flatnonzero((x[:-1] <= 0) & (x[1:] > 0))
    if len(index) < 4:
        raise AssertionError('No sustained positive crossings')
    times = index - x[index] / (x[index+1]-x[index])
    return rate * (len(times)-1) / (times[-1]-times[0])


class TransportBoundaryTests(unittest.TestCase):
    def test_linear_speed_ramp_has_analytic_area_and_freeze_does_not_consume_it(self):
        for mode in range(6):
            with Transport(np.zeros((48000, 2), 'float32'), 44100, mode, output_rate=48000) as h:
                h.seek(1000)
                # N samples include increments 1/N..N/N: area=(N+1)/2.
                h.set(0, 0)
                h.render(257, [(0, 0, 1., 257)])
                expected = 1000 + (257+1)/2 * 44100/48000
                self.assertAlmostEqual(h.info()['source_position'], expected, places=8)
                h.set(0, 0)
                held = h.info()['source_position']
                render(h, 8113)
                self.assertEqual(h.info()['source_position'], held)
                h.set(.000001, 0)
                render(h, 4001)
                self.assertAlmostEqual(h.info()['source_position'], held+.000001*4001*44100/48000, places=8)
                h.set(4, 0)
                h.render(257)
                self.assertAlmostEqual(h.info()['source_position'], held+.000001*4001*44100/48000+4*257*44100/48000, places=8)

    def test_bad_batch_preserves_all_later_output_not_just_info(self):
        rng = np.random.default_rng(26091841)
        source = rng.normal(0, .02, (8192, 2)).astype('float32')
        bad = [ [(0,0,1.,0),(0,1,float('nan'),0)],
                [(0,0,.5,0),(0,1,25.,0)], [(0,0,0.,0),(0,2,1.,0)],
                [(255,0,0.,0),(254,0,1.,0)] ]
        for mode in range(6):
            with Transport(source,48000,mode) as a, Transport(source,48000,mode) as b:
                a.set(0,0);b.set(0,0);a.seek(2000);b.seek(2000)
                np.testing.assert_array_equal(a.render(173),b.render(173))
                for events in bad:
                    before=a.info()
                    with self.assertRaises(ValueError): a.render(257,events)
                    self.assertEqual(a.info(),before)
                    np.testing.assert_array_equal(a.render(257),b.render(257))

    def test_silence_dc_eof_and_seek_replay(self):
        for mode in range(6):
            for value in (0.,.125):
                source=np.full((24000,2), value, 'float32')
                with Transport(source,48000,mode) as h:
                    h.seek(12000);h.set(0,0);a=render(h,8193)
                    np.testing.assert_allclose(a[-1000:],value,atol=1e-6,rtol=0)
                    h.seek(12000);b=render(h,8193,32)
                    np.testing.assert_array_equal(a,b)
                    h.seek(len(source));h.set(4,0);out=render(h,18000)
                    self.assertEqual(h.info()['ended'],1)
                    np.testing.assert_array_equal(out,np.zeros_like(out))
                    h.seek(10000);h.set(0,0)
                    self.assertEqual(h.info()['ended'],0)
            for size in (1,17):
                with Transport(np.full((size,2),.1,'float32'),48000,mode) as h:
                    h.set(4,24);y=render(h,17000)
                    self.assertTrue(np.isfinite(y).all());self.assertEqual(h.info()['ended'],1)

    def test_pitch_ramp_progresses_during_hold_and_resume_uses_held_anchor(self):
        rate=48000;t=np.arange(rate*2)/rate;x=.1*np.cos(2*np.pi*223*t)
        source=np.c_[x,-.375*x].astype('float32')
        for mode in range(6):
            with Transport(source,rate,mode) as h:
                h.seek(24000);h.set(0,0);before=render(h,24000)
                h.render(0,[(0,1,12.,2400)])
                after=render(h,24000)
                self.assertEqual(h.info()['source_position'],24000)
                self.assertEqual(h.info()['pitch_semitones'],12.)
                for audio,expected in ((before,223.),(after,446.)):
                    f=crossing_frequency(audio[-12000:,0].astype('float64'),rate)
                    self.assertLess(abs(1200*np.log2(f/expected)),5.)
                h.set(1,0);h.render(257)
                self.assertEqual(h.info()['source_position'],24257)

if __name__=='__main__':unittest.main()
