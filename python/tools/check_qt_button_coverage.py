#!/usr/bin/env python3
"""Static Qt button coverage audit for the desktop shell.

The script scans button attributes created in ``ui/qt/pages.py`` and checks
whether they are referenced by ``clicked.connect``/``toggled.connect`` calls in
``ui/qt/controller.py`` or ``ui/qt/main_window.py``.

It is intentionally conservative: dynamic lambda indirection is treated as
covered when the button attribute name appears near a ``connect`` call.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "grace_pipeline" / "ui" / "qt" / "pages.py"
CONTROLLER = ROOT / "grace_pipeline" / "ui" / "qt" / "controller.py"
MAIN_WINDOW = ROOT / "grace_pipeline" / "ui" / "qt" / "main_window.py"

BUTTON_RE = re.compile(r"self\.(btn_[A-Za-z0-9_]+)\s*=\s*(?:QPushButton|QToolButton|QCheckBox|QRadioButton)\(")
CONNECT_RE = re.compile(r"(?:self|w|page|dashboard|monitor|window)\.([A-Za-z0-9_]+).*?\.connect\(")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def main() -> int:
    page_text = _read(PAGES)
    bind_text = _read(CONTROLLER) + "\n" + _read(MAIN_WINDOW)
    buttons = sorted(set(BUTTON_RE.findall(page_text)))
    connected = set(CONNECT_RE.findall(bind_text))

    # A few buttons are wired indirectly or by top-level aliases.
    indirect = {
        "btn_run_full",
        "btn_pause_run",
        "btn_stop_run",
        "btn_console_run",
    }
    uncovered = [name for name in buttons if name not in connected and name not in indirect]

    print(f"Buttons discovered: {len(buttons)}")
    print(f"Buttons referenced by connect(): {len(connected)}")
    if uncovered:
        print("\nPotentially uncovered buttons:")
        for name in uncovered:
            print(f"  - {name}")
        return 1
    print("All discovered buttons appear to be covered by controller/main-window bindings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
