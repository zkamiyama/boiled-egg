"""Native bindings, worker lifecycle, Qt controls and exact existing-SDK probes."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import queue
import tempfile
import time
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QAudioDevice
import app
from native import Transport
from worker import Settings,PlayerWorker
import sdk_compare

QT=QApplication.instance() or QApplication([])
def tone(rate=48000,seconds=1.):
    t=np.arange(round(rate*seconds))/rate
    x=.1*np.cos(2*np.pi*223*t)
    return np.c_[x,-.375*x].astype('float32')
class FakeIO:
    def __init__(self):self.data=bytearray()
    def write(self,b):
        n=min(7,len(b));self.data.extend(b[:n]);return n
class FakeSink:
    def __init__(self):self.paused=False
    def bytesFree(self):return 11
    def suspend(self):self.paused=True
    def resume(self):self.paused=False
    def reset(self):pass
    def deleteLater(self):pass

class AppTests(unittest.TestCase):
    def test_pitch_zero_and_speed_zero_are_independent(self):
        for mode in range(6):
            with Transport(tone(),48000,mode=mode) as h:
                h.seek(12000);h.set(0,0);a=h.render(4000);b=h.info()
                self.assertEqual((b['source_position'],b['speed'],b['pitch_semitones']),(12000,0,0))
                self.assertGreater(abs(a).max(),1e-3)
                h.set(0,7,ramp=64);h.render(256)
                self.assertEqual(h.info()['pitch_semitones'],7)
                self.assertEqual(h.info()['source_position'],12000)
    def test_unordered_invalid_batch_is_atomic(self):
        with Transport(tone(),48000) as a,Transport(tone(),48000) as b:
            with self.assertRaises(ValueError):a.render(256,[(10,0,0,0),(1,1,7,0)])
            self.assertEqual(a.info()['output_frames'],0)
            np.testing.assert_array_equal(a.render(256),b.render(256))
            for v in (-1,float('nan'),float('inf'),4.01):
                with self.assertRaises(ValueError):a.set(v,0)
    def test_worker_invalid_load_preserves_handle_source_and_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            valid=Path(tmp)/'ok.wav';bad=Path(tmp)/'bad.wav'
            sf.write(valid,tone(),48000,subtype='FLOAT');sf.write(bad,tone(),1000,subtype='FLOAT')
            w=PlayerWorker()
            try:
                w._apply('load',valid);old=w.handle;source=w.source;setting=w.settings
                with self.assertRaises(ValueError):w._apply('load',bad)
                self.assertIs(w.handle,old);self.assertIs(w.source,source);self.assertEqual(w.settings,setting)
                old.render(64)
                with self.assertRaises(ValueError):w._apply('seek',-1)
                self.assertEqual(w.epoch,1)
            finally:
                if w.handle:w.handle.close()
    def test_worker_freeze_export_is_finite_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'in.wav';dest=Path(tmp)/'hold.wav';sf.write(p,tone(),48000,subtype='FLOAT')
            w=PlayerWorker()
            try:
                w._apply('load',p);w._apply('settings',Settings(speed=0));w._apply('seek',.25)
                w._export(dest,.25);s=sf.info(dest)
                self.assertEqual((s.frames,s.channels,s.subtype),(12000,2,'FLOAT'))
                self.assertEqual(w.handle.info()['source_position'],12000)
                saved=dest.read_bytes()
                with self.assertRaises(ValueError):w._export(dest,.25)
                self.assertEqual(dest.read_bytes(),saved)
                w.quit_event.set();other=Path(tmp)/'cancel.wav'
                with self.assertRaises(InterruptedError):w._export(other,1)
                self.assertFalse(other.exists())
            finally:
                if w.handle:w.handle.close()
    def test_single_owner_thread_queue_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'in.wav';sf.write(p,tone(),48000,subtype='FLOAT')
            w=PlayerWorker();w.start()
            try:
                w.command('load',str(p));deadline=time.monotonic()+4
                while time.monotonic()<deadline:
                    kind,data=w.messages.get(timeout=4)
                    if kind=='ready':break
                w.command('settings',Settings(speed=0));w.command('play')
                epoch,data,state=w.audio.get(timeout=4)
                self.assertEqual(state['speed'],0);self.assertEqual(len(data),1024*2*4)
                time.sleep(.08);self.assertLessEqual(w.audio.qsize(),2)
                w.command('pause')
            finally:w.stop_worker();w.join(4)
            self.assertFalse(w.is_alive());self.assertIsNone(w.handle)
    def test_qt_partial_writes_preserve_every_byte_and_epoch(self):
        q=queue.Queue();pump=app.OutputPump(q);pump.sink=FakeSink();pump.io=FakeIO();pump.epoch=2;pump.running=True
        stale=b'old!';new=bytes(range(200));q.put((1,stale,{}));q.put((2,new,{}))
        for _ in range(50):pump.tick()
        self.assertEqual(bytes(pump.io.data),new);self.assertFalse(pump.pending)
        pump.pause();q.put((2,b'pause',{}));pump.tick();self.assertEqual(bytes(pump.io.data),new)
    def test_qt_no_device_is_explicit(self):
        p=app.OutputPump(queue.Queue());errors=[];p.error.connect(errors.append)
        self.assertFalse(p.configure(QAudioDevice(),48000,2,0));self.assertFalse(p.play());self.assertEqual(len(errors),1)
    def test_qt_controls_hold_not_pause_and_unity(self):
        w=app.MainWindow()
        try:
            self.assertEqual(w.speed.value(),1);self.assertEqual(w.pitch.value(),0)
            w.speed.setValue(.73);w.freeze();self.assertEqual(w.speed.value(),0);self.assertFalse(w.playing)
            w.freeze();self.assertEqual(w.speed.value(),.73)
            w.pitch.setValue(7);w.reset_controls();self.assertEqual(w.pitch.value(),0)
            w.policy.setCurrentIndex(1);w.formant.setValue(2);w.mode.setCurrentIndex(3)
            self.assertEqual(w.policy.currentIndex(),0);self.assertEqual(w.formant.value(),0)
            self.assertFalse(w.policy.isEnabled())
            self.assertEqual(w.mode.count(),6);self.assertEqual(w.sdk_mode.count(),5)
        finally:w.close();QT.processEvents()
        self.assertFalse(w.worker.is_alive())
    def test_sdk_rejects_unsupported_no_substitution(self):
        for index,speed,pitch,policy,formant in [(3,0,0,'off',0),(3,4,0,'off',0),(0,1,0,'harmonic',0),(4,1,13,'off',0),(0,1,0,'off',1)]:
            with self.assertRaises(ValueError):sdk_compare.validate(index,speed,pitch,policy,formant)
    def test_existing_sdk_all_modes_raw_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'in.wav';sf.write(p,tone(seconds=.25),48000,subtype='FLOAT')
            for mode in range(5):
                for operation,(speed,pitch) in enumerate(((1.,0.),(.8,0.),(1.25,0.),(1.,7.))):
                    out=Path(tmp)/f'{mode}-{operation}.wav';r=sdk_compare.render(p,out,mode,speed,pitch)
                    self.assertEqual(r['output_frames'],round(12000/speed));self.assertEqual(r['channels'],2)
                    self.assertTrue(out.with_suffix('.wav.json').is_file())
                    with self.assertRaises(FileExistsError):sdk_compare.render(p,out,mode,speed,pitch)
            (Path(tmp)/'existing.wav.json').write_text('keep')
            with self.assertRaises(FileExistsError):sdk_compare.render(p,Path(tmp)/'existing.wav',0,1,0)
    def test_settings_limits_and_unavailable_formants(self):
        for args in (dict(speed=-1),dict(pitch=25),dict(mode=3,policy=1),dict(formant=1),dict(output_rate=22050)):
            with self.assertRaises(ValueError):Settings(**args)
        for speed in (0,.00001,1,4):self.assertEqual(Settings(speed=speed).speed,speed)
if __name__=='__main__':unittest.main()
