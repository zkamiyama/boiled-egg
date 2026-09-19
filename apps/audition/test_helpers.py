"""Shared Qt test teardown: assert asynchronous close really finishes."""
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication

def close_window(window):
    root=Path(window.temporary.name)
    window.close()
    deadline=time.monotonic()+5
    while not window.closed and time.monotonic()<deadline:
        QApplication.processEvents();time.sleep(.005)
    assert window.closed, 'Window did not finish cancelling its jobs'
    assert not window.worker.is_alive(), 'Native owner survived close'
    assert not root.exists(), 'Temporary files survived completed close'
