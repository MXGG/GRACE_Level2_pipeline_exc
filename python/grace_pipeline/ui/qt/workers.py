"""Qt background workers used by the desktop shell."""

from __future__ import annotations

import contextlib
import io
import traceback
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, QThread, Signal


class SignalStream(io.TextIOBase):
    """File-like object that forwards text to a Qt signal."""

    def __init__(self, signal):
        super().__init__()
        self.signal = signal

    def writable(self):
        return True

    def write(self, text):
        if text is None:
            return 0
        text = str(text)
        if text:
            self.signal.emit(text)
        return len(text)

    def flush(self):
        return None


class TaskWorker(QThread):
    """Generic task worker with log/progress signals."""

    log = Signal(str)
    progress = Signal(float, str)
    status = Signal(str)
    result = Signal(object)
    failed = Signal(str)

    def __init__(self, func: Callable[[], Any], parent: Optional[QObject] = None):
        super().__init__(parent)
        self._func = func
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        try:
            out = self._func()
            self.result.emit(out)
        except Exception:
            self.failed.emit(traceback.format_exc())


class RedirectedTaskWorker(TaskWorker):
    """Task worker that redirects stdout/stderr to the log signal."""

    def run(self):
        stream = SignalStream(self.log)
        try:
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                out = self._func()
            self.result.emit(out)
        except Exception:
            self.failed.emit(traceback.format_exc())
