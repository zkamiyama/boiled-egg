"""Removal gap, isolated async query and malformed-reply negative controls."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from audio_devices import PulseDeviceMonitor, parse_sink_names, MAX_REPLY_BYTES
from app import MainWindow
from test_devices import Endpoint
from test_helpers import close_window

QT = QApplication.instance() or QApplication([])


def spin(predicate):
    deadline = time.monotonic() + 5
    while not predicate() and time.monotonic() < deadline:
        QT.processEvents(); time.sleep(.002)
    if not predicate(): raise AssertionError('Async device query did not finish')


class PulseDeviceTests(unittest.TestCase):
    def test_empty_is_valid_but_invalid_and_duplicate_are_not_removals(self):
        self.assertEqual(parse_sink_names(b'[]'), frozenset())
        self.assertEqual(parse_sink_names(b'[{"name":"left"}]'), frozenset([b'left']))
        for raw in (b'{}', b'null', b'not json', b'[{}]', b'[{"name":1}]',
                    b'[{"name":"same"},{"name":"same"}]', b' '*(MAX_REPLY_BYTES+1)):
            with self.assertRaises((ValueError, TypeError)): parse_sink_names(raw)

    def test_stale_qt_cache_is_filtered_without_reroute_or_source_reset(self):
        a, b = Endpoint(b'a','A'), Endpoint(b'b','B')
        with patch('app.QMediaDevices.audioOutputs', return_value=[a,b]):
            w = MainWindow(language='en')
            try:
                w.pulse_monitor.stop()
                w.pulse_devices_changed(frozenset([b'a',b'b']))
                w.native_ready = True; w.playing = True
                with patch.object(w.worker,'command') as commands:
                    w.pulse_devices_changed(frozenset([b'b']))
                    self.assertIsNone(w.selected_device()); self.assertFalse(w.playing)
                    self.assertTrue(w.native_ready)
                    self.assertEqual(commands.call_args.args, ('pause',None))
                    w.pulse_devices_changed(frozenset([b'a',b'b']))
                    self.assertIsNone(w.selected_device())
                    self.assertNotIn('seek',[c.args[0] for c in commands.call_args_list])
            finally: close_window(w)

    def test_unidentified_other_backend_is_not_filtered(self):
        a = Endpoint(b'non-pulse-id', 'Other backend')
        with patch('app.QMediaDevices.audioOutputs', return_value=[a]):
            w = MainWindow(language='en')
            try:
                w.pulse_monitor.stop(); w.pulse_devices_changed(frozenset([b'alsa-name']))
                self.assertIsNone(w._pulse_ids); self.assertIs(w.selected_device(),a)
            finally: close_window(w)

    def test_real_async_read_failure_and_close_do_not_emit_false_empty_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'endpoints.json'; path.write_text('[{"name":"a"}]')
            code = 'import pathlib,sys;sys.stdout.write(pathlib.Path(sys.argv[1]).read_text())'
            monitor = PulseDeviceMonitor(program=sys.executable, arguments=['-c',code,str(path)], interval=10000)
            seen=[]; monitor.snapshot.connect(seen.append)
            try:
                spin(lambda:len(seen)==1)
                self.assertEqual(seen, [frozenset([b'a'])])
                path.write_text('broken'); monitor.request(); spin(lambda:not monitor.running)
                self.assertEqual(len(seen),1); self.assertIsNotNone(monitor.last_error)
                path.write_text('[]'); monitor.request(); spin(lambda:len(seen)==2)
                self.assertEqual(seen[-1],frozenset())
                monitor.stop(); monitor.request(); self.assertFalse(monitor.running)
            finally: monitor.stop(); spin(lambda:not monitor.running)

    def test_inflight_query_is_cancelled_without_blocking_or_publishing(self):
        monitor = PulseDeviceMonitor(program=sys.executable, arguments=['-c','import time;time.sleep(30)'])
        seen=[]; monitor.snapshot.connect(seen.append)
        try:
            spin(lambda:monitor.running)
            begin=time.monotonic(); monitor.stop()
            self.assertLess(time.monotonic()-begin,.1)
            spin(lambda:not monitor.running); self.assertEqual(seen,[])
        finally: monitor.stop(); spin(lambda:not monitor.running)


if __name__ == '__main__': unittest.main()
