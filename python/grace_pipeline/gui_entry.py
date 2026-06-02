"""
GUI entry point for PyInstaller windowed build.
"""

import os
import sys
import multiprocessing as mp
import importlib
import importlib.util


def _load_gui():
    try:
        from grace_pipeline.gui import start_gui  # type: ignore
        return start_gui
    except Exception:
        # Fallback for non-frozen or misconfigured paths
        here = os.path.abspath(os.path.dirname(__file__))
        parent = os.path.abspath(os.path.join(here, os.pardir))
        grand = os.path.abspath(os.path.join(parent, os.pardir))
        candidates = []
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(meipass)
            candidates.append(os.path.join(meipass, "grace_pipeline"))
        candidates.extend([here, parent, grand, os.path.join(here, "grace_pipeline")])
        for p in candidates:
            if p and os.path.isdir(p) and p not in sys.path:
                sys.path.insert(0, p)
        try:
            from grace_pipeline.gui import start_gui  # type: ignore
            return start_gui
        except Exception:
            # As a last resort, load gui.py from disk if present
            for base in [meipass, here, parent, grand]:
                if not base:
                    continue
                fp = os.path.join(base, "grace_pipeline", "gui.py")
                if os.path.isfile(fp):
                    spec = importlib.util.spec_from_file_location("grace_pipeline.gui", fp)
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        sys.modules["grace_pipeline.gui"] = mod
                        spec.loader.exec_module(mod)
                        return getattr(mod, "start_gui")
            raise


start_gui = _load_gui()


if __name__ == "__main__":
    # Prevent spawned worker processes from launching GUI, but allow workers to run.
    mp.freeze_support()
    if mp.current_process().name == "MainProcess":
        start_gui()
