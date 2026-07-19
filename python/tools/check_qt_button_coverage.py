#!/usr/bin/env python3
"""Static Qt button coverage audit for the desktop shell.

The script scans button attributes created in ``ui/qt/pages.py`` and checks
whether they appear in controller/main-window/global-monitor binding code near a
Qt ``connect()`` call. It intentionally supports the local patterns used by the
desktop shell, including tuple/list driven loops where the button attribute is
listed several lines before ``btn.clicked.connect(...)``.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "grace_pipeline" / "ui" / "qt" / "pages.py"
CONTROLLER = ROOT / "grace_pipeline" / "ui" / "qt" / "controller.py"
MAIN_WINDOW = ROOT / "grace_pipeline" / "ui" / "qt" / "main_window.py"
GLOBAL_MONITOR = ROOT / "grace_pipeline" / "ui" / "qt" / "global_monitor.py"

BUTTON_RE = re.compile(r"self\.(btn_[A-Za-z0-9_]+)\s*=\s*(?:QPushButton|QToolButton|QCheckBox|QRadioButton)\(")
CONNECT_TEXT = ".connect("


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace") if path.exists() else ""


def _is_connected(button_name: str, binding_lines: list[str]) -> bool:
    for idx, line in enumerate(binding_lines):
        if button_name not in line:
            continue
        window = binding_lines[max(0, idx - 5) : min(len(binding_lines), idx + 41)]
        if any(CONNECT_TEXT in candidate for candidate in window):
            return True
    return False


def main() -> int:
    page_text = _read(PAGES)
    bind_text = "\n".join(_read(path) for path in (CONTROLLER, MAIN_WINDOW, GLOBAL_MONITOR))
    binding_lines = bind_text.splitlines()
    buttons = sorted(set(BUTTON_RE.findall(page_text)))
    connected = {name for name in buttons if _is_connected(name, binding_lines)}

    # A few buttons are wired indirectly or intentionally hidden behind the
    # global run monitor compatibility layer.
    indirect = {
        "btn_run_full",
        "btn_pause_run",
        "btn_stop_run",
        "btn_console_run",
    }
    uncovered = [name for name in buttons if name not in connected and name not in indirect]

    print(f"Buttons discovered: {len(buttons)}")
    print(f"Buttons covered by nearby connect(): {len(connected)}")
    if uncovered:
        print("\nPotentially uncovered buttons:")
        for name in uncovered:
            print(f"  - {name}")
        return 1
    print("All discovered buttons appear to be covered by controller/main-window/global-monitor bindings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
