"""Output errors, stale callbacks and recovery; no sound hardware is assumed."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import queue
import unittest
from PySide6.QtMultimedia import QAudio
from PySide6.QtWidgets import QApplication
from audio_output import OutputPump
from app import MainWindow
QT=QApplication.instance() or QApplication([])
class Sink:
    def __init__(self):self.current=QAudio.IdleState;self.failure=QAudio.NoError
    def state(self):return self.current
    def error(self):return self.failure
    def resume(self):pass
    def suspend(self):pass
    def reset(self):self.current=QAudio.StoppedState
    def deleteLater(self):pass
    def bytesFree(self):return 32
class Device:
    def write(self,data):return -1
class OutputTests(unittest.TestCase):
    def test_device_failure_invalidates_writer_and_old_signals_are_ignored(self):
        p=OutputPump(queue.Queue());p.sink=Sink();p.io=Device();messages=[];p.error.connect(messages.append)
        self.assertTrue(p.play());generation=p.generation
        p.device_state(generation,QAudio.IdleState);self.assertTrue(p.running)
        p.sink.failure=QAudio.IOError;p.device_state(generation,QAudio.StoppedState)
        self.assertFalse(p.running);self.assertIsNone(p.io);self.assertEqual(len(messages),1)
        p.close();p.sink=Sink();p.io=Device();self.assertTrue(p.play())
        p.device_state(generation,QAudio.StoppedState);self.assertTrue(p.running)
        p.close()
    def test_resume_of_stopped_device_is_not_success(self):
        p=OutputPump(queue.Queue());p.sink=Sink();p.io=Device();p.sink.current=QAudio.StoppedState
        self.assertFalse(p.play());self.assertFalse(p.running);p.close()
    def test_write_failure_and_ui_stop_the_worker_without_destroying_source(self):
        w=MainWindow()
        try:
            w.playing=True;w.pump.sink=Sink();w.pump.io=Device();w.pump.running=True
            w.worker.audio.put((w.pump.epoch,b'abcdefgh',{}))
            # This injected block has no telemetry; only the write-error path is tested.
            w.pump.telemetry.disconnect(w.telemetry)
            w.pump.tick()
            self.assertFalse(w.playing);self.assertFalse(w.pump.running);self.assertIsNone(w.pump.io)
            self.assertIn('書込み',w.log.toPlainText())
        finally:w.close();QT.processEvents()
if __name__=='__main__':unittest.main()
