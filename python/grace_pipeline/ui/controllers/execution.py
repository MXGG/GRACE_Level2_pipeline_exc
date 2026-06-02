"""Execution/run-loop service extracted from GUI layer."""

import os
import sys
import threading
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import messagebox


def on_run(self):
    # 1. Update Config from GUI
    if not getattr(self, "_config_ready", False):
        messagebox.showwarning("Config", "Please load/select a config file before running.")
        return
    if getattr(self, "_active_scope", None):
        self._msg_warn("Run", f"Another task is running: {self._active_scope}")
        return
    try:
        self._update_config()
    except Exception as e:
        messagebox.showerror("Configuration Error", str(e))
        return

    # 2. Disable UI (scope-aware)
    self._set_busy_scope("filters", indeterminate=False)
    self.log_text.configure(state="normal")
    self.log_text.delete(1.0, tk.END)
    self.log_text.configure(state="disabled")

    # 3. Start Thread
    t = threading.Thread(target=self._run_thread)
    t.daemon = True
    t.start()


def on_run_all(self):
    # Enable all major modules before running
    try:
        if hasattr(self, "var_basin_enable"):
            self.var_basin_enable.set(True)
        if hasattr(self, "var_save_monthly_mat"):
            self.var_save_monthly_mat.set(True)
    except Exception:
        pass
    self.on_run()


def _run_thread(self):
    # Redirect stdout/stderr
    old_stdout = sys.stdout
    old_stderr = sys.stderr

    log_fp = None
    try:
        out_root = Path(self.cfg.path.OUTPUT)
        log_dir = out_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_fp = open(log_dir / f"gui_run_{ts}.log", "w", encoding="utf-8")
    except Exception:
        log_fp = None

    redirector_cls = getattr(self, "_TextRedirector", None)
    if redirector_cls is None:
        raise RuntimeError("TextRedirector class is not attached to GUI instance.")
    sys.stdout = redirector_cls(self.log_text, "stdout", log_fp=log_fp)
    sys.stderr = redirector_cls(self.log_text, "stderr", log_fp=log_fp)
    os.environ.setdefault("TQDM_DISABLE", "1")

    try:
        print("--- Starting Pipeline ---")
        print(f"Config Output: {self.cfg.path.OUTPUT}")
        from grace_pipeline.app.pipeline import run_pipeline

        def _progress_cb(done, total):
            try:
                self.root.after(0, lambda: self._update_progress(done, total))
            except Exception:
                pass

        run_pipeline(self.cfg, pause_event=self.pause_event, stop_event=self.stop_event, progress_cb=_progress_cb)

        print("--- Pipeline Finished Successfully ---")
        self.root.after(0, lambda: messagebox.showinfo("Success", "Pipeline processing completed."))

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback

        traceback.print_exc()
        self.root.after(0, lambda: messagebox.showerror("Error", f"Pipeline failed:\n{e}"))

    finally:
        # Restore
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        if log_fp:
            try:
                log_fp.close()
            except Exception:
                pass

        # Reset UI
        self.root.after(0, self._reset_ui)


def _reset_ui(self):
    self._active_scope = None
    for bar in getattr(self, "_progress_bars", []):
        try:
            bar["value"] = 0
        except Exception:
            pass
    for var in getattr(self, "_progress_vars", []):
        try:
            var.set("0%")
        except Exception:
            pass
    for btn in getattr(self, "_run_buttons", []):
        try:
            btn.config(state="normal")
        except Exception:
            pass
    if hasattr(self, "btn_run_all"):
        self.btn_run_all.config(state="normal")
    for btn in getattr(self, "_pause_buttons", []):
        try:
            btn.config(state="disabled", text="Pause")
        except Exception:
            pass
    for ev in self._scope_events.values():
        try:
            ev["pause"].clear()
            ev["stop"].clear()
        except Exception:
            pass
    self.pause_event, self.stop_event = self._get_scope_events("all")
    for btn in getattr(self, "_stop_buttons", []):
        try:
            btn.config(state="disabled")
        except Exception:
            pass
