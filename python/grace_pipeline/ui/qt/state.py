"""Qt application state and signaling primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event
from typing import Any, Optional

from PySide6.QtCore import QObject, Signal


@dataclass
class RunSnapshot:
    """Serializable snapshot of the current run state."""

    scope: str = "idle"
    status: str = "ready"
    phase: str = "idle"
    message: str = ""
    progress: float = 0.0
    paused: bool = False
    stopped: bool = False
    job_id: str = ""
    current_page: str = "dashboard"


@dataclass
class PreviewSnapshot:
    """Lightweight preview payload for the preview page."""

    path: str = ""
    shape: tuple[int, int, int] = (0, 0, 0)
    lon: Any = None
    lat: Any = None
    t: Any = None
    meta: dict[str, Any] = field(default_factory=dict)
    active_var: str = ""
    index: int = 0
    title: str = ""
    summary: str = ""


class QtAppState(QObject):
    """Shared state object for the Qt shell."""

    configChanged = Signal(object)
    runStateChanged = Signal(object)
    logAppended = Signal(str, str)
    progressChanged = Signal(str, float, str)
    pageChanged = Signal(str)
    previewChanged = Signal(object)

    def __init__(self, config: Any = None):
        super().__init__()
        self.config = config
        self.config_path: Optional[str] = None
        self.run = RunSnapshot()
        self.preview = PreviewSnapshot()
        self._scope_events: dict[str, dict[str, Event]] = {}

    def ensure_scope_events(self, scope: str) -> tuple[Event, Event]:
        scope = str(scope or "all")
        events = self._scope_events.get(scope)
        if not isinstance(events, dict):
            events = {"pause": Event(), "stop": Event()}
            self._scope_events[scope] = events
        return events["pause"], events["stop"]

    def set_config(self, config: Any, *, path: Optional[str] = None):
        self.config = config
        self.config_path = path
        self.configChanged.emit(config)

    def set_page(self, page_key: str):
        self.run.current_page = str(page_key or "dashboard")
        self.pageChanged.emit(self.run.current_page)

    def set_run_state(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self.run, key):
                setattr(self.run, key, value)
        self.runStateChanged.emit(self.run)

    def append_log(self, message: str, tag: str = "stdout"):
        self.logAppended.emit(str(message), str(tag))

    def set_progress(self, scope: str, pct: float, text: Optional[str] = None):
        self.progressChanged.emit(str(scope or "all"), float(pct), text or "")

    def set_preview(self, preview: PreviewSnapshot):
        self.preview = preview
        self.previewChanged.emit(preview)
