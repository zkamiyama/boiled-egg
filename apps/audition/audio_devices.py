"""Read-only PulseAudio endpoint snapshots for the Qt 6.9 removal-notification gap.

Qt's public device cache may retain the last sink after its removal. On Linux,
when pactl is installed, a bounded asynchronous query supplies an authoritative
name set. The UI intersects only an identified Pulse namespace; it never selects
or reroutes an output. No subprocess or enumeration runs on the DSP owner thread.
"""
from __future__ import annotations
import json
import shutil
import sys
from PySide6.QtCore import QObject, QProcess, QTimer, Signal

MAX_REPLY_BYTES = 262144


def parse_sink_names(data: bytes) -> frozenset[bytes]:
    if len(data) > MAX_REPLY_BYTES:
        raise ValueError('PulseAudio endpoint reply exceeds the bounded limit')
    rows = json.loads(data)
    if not isinstance(rows, list) or len(rows) > 1024:
        raise ValueError('Invalid PulseAudio endpoint list')
    names = []
    for row in rows:
        name = row.get('name') if isinstance(row, dict) else None
        if not isinstance(name, str) or not name or '\x00' in name or len(name) > 4096:
            raise ValueError('Invalid PulseAudio endpoint name')
        names.append(name.encode('utf-8'))
    if len(names) != len(set(names)):
        raise ValueError('Duplicate PulseAudio endpoint name')
    return frozenset(names)


class PulseDeviceMonitor(QObject):
    """One async read at most per 500ms; 2s timeout and bounded stdout/stderr.

    pactl is an optional Linux/Pulse guard; unavailable/unreachable/invalid replies
    are NOT empty-device snapshots. The standard Qt signal remains connected.
    """
    snapshot = Signal(object)

    def __init__(self, parent=None, *, program=None, arguments=None, interval=500):
        super().__init__(parent)
        self.program = program if program is not None else (shutil.which('pactl') if sys.platform.startswith('linux') else None)
        self.arguments = ['--format=json', 'list', 'sinks'] if arguments is None else list(arguments)
        self.stopped = False
        self.last_error = None
        self.accepted_snapshots = 0
        self.reply = bytearray()
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.readyReadStandardError.connect(self._drain_errors)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._error)
        self.timer = QTimer(self); self.timer.setInterval(max(100, interval))
        self.timer.timeout.connect(self.request)
        self.deadline = QTimer(self); self.deadline.setSingleShot(True)
        self.deadline.setInterval(2000); self.deadline.timeout.connect(self._timeout)
        if self.program:
            self.timer.start(); QTimer.singleShot(0, self.request)

    @property
    def running(self):
        return self.process.state() != QProcess.NotRunning

    def request(self):
        if self.stopped or not self.program or self.running:
            return
        self.reply.clear(); self.last_error = None
        self.process.start(self.program, self.arguments)
        self.deadline.start()

    def _read(self):
        chunk = bytes(self.process.readAllStandardOutput())
        if len(self.reply) + len(chunk) > MAX_REPLY_BYTES:
            self.last_error = 'oversized endpoint reply'; self.process.kill()
            return
        self.reply.extend(chunk)

    def _drain_errors(self):
        # Do not accumulate an unbounded subprocess diagnostic stream.
        self.process.readAllStandardError()

    def _error(self, error):
        self.last_error = str(error)
        if not self.running: self.deadline.stop()

    def _timeout(self):
        self.last_error = 'endpoint query timed out'; self.process.kill()

    def _finished(self, code, status):
        self.deadline.stop(); self._read(); self._drain_errors()
        if self.stopped or code != 0 or status != QProcess.NormalExit or self.last_error:
            return
        try:
            names = parse_sink_names(bytes(self.reply))
        except (ValueError, TypeError, UnicodeError) as exc:
            self.last_error = str(exc)
            return
        self.accepted_snapshots += 1
        self.snapshot.emit(names)

    def stop(self):
        self.stopped = True; self.timer.stop(); self.deadline.stop()
        if self.running: self.process.kill()
