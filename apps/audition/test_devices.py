"""Device identity and hotplug tests; no physical hardware claim."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from app import MainWindow
from test_helpers import close_window

QT=QApplication.instance() or QApplication([])

class Endpoint:
    def __init__(self, identity, name): self.identity=identity; self.name=name
    def id(self): return self.identity
    def description(self): return self.name

class DeviceTests(unittest.TestCase):
    def window(self):
        a,b=Endpoint(b'a','A'),Endpoint(b'b','B')
        with patch('app.QMediaDevices.audioOutputs',return_value=[a,b]): w=MainWindow(language='en')
        self.addCleanup(close_window,w)
        return w,a,b

    def test_reordering_keeps_selected_device_without_resetting_dsp(self):
        w,a,b=self.window()
        with patch.object(w.worker,'command') as commands, patch.object(w.pump,'close') as close:
            with patch('app.QMediaDevices.audioOutputs',return_value=[b,a]): w.refresh_devices()
            self.assertEqual(w.device.currentIndex(),1)
            self.assertEqual(w.selected_device_id,b'a')
            commands.assert_not_called(); close.assert_not_called()

    def test_unplug_stops_and_never_reroutes_to_remaining_device(self):
        w,a,b=self.window();w.playing=True;w.native_ready=True
        with patch.object(w.worker,'command') as commands, patch.object(w.pump,'close') as close:
            with patch('app.QMediaDevices.audioOutputs',return_value=[b]): w.refresh_devices()
            self.assertIsNone(w.selected_device());self.assertIsNone(w.selected_device_id)
            self.assertEqual(w.device.currentIndex(),-1);self.assertFalse(w.playing)
            self.assertTrue(w.native_ready);close.assert_called_once()
            self.assertEqual(commands.call_args.args,('pause',None))
        self.assertIn('disconnected',w.log.toPlainText())
        w.change_language('ja');self.assertIn('切断',w.log.toPlainText())

    def test_new_device_selection_reuses_stream_without_seek_and_retranslation_is_current(self):
        w,a,b=self.window();w.stream_format=dict(rate=48000,channels=2,epoch=7)
        with patch('app.QMediaDevices.audioOutputs',return_value=[]):w.refresh_devices()
        with patch('app.QMediaDevices.audioOutputs',return_value=[b]):w.refresh_devices()
        self.assertEqual(w.device.currentIndex(),-1)
        w.change_language('ja');self.assertEqual(w.device.itemText(0),'B')
        with patch.object(w.pump,'configure',return_value=False) as configure, patch.object(w.worker,'command') as commands:
            w.device.setCurrentIndex(0)
            configure.assert_called_once_with(b,**w.stream_format)
            self.assertEqual(w.selected_device_id,b'b')
            self.assertNotIn('seek',[c.args[0] for c in commands.call_args_list])

if __name__=='__main__':unittest.main()
