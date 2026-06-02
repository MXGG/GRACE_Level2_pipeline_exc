"""Tk text redirection helper."""

import queue


class TextRedirector:
    """Redirect stdout/stderr to a Tkinter Text widget."""

    def __init__(self, widget, tag="stdout", max_lines=4000, log_fp=None):
        self.widget = widget
        self.tag = tag
        self.max_lines = max_lines
        self.log_fp = log_fp
        self._queue = queue.Queue()
        self._flush_scheduled = False

    def write(self, text):
        msg = text.replace("\r", "\n")
        msg = self._strip_ansi(msg)
        if self.log_fp:
            try:
                self.log_fp.write(msg)
            except Exception:
                pass
        self._queue.put(msg)
        if not self._flush_scheduled:
            self._flush_scheduled = True
            try:
                self.widget.after(100, self._flush_queue)
            except Exception:
                self._flush_scheduled = False

    def _flush_queue(self):
        try:
            chunks = []
            while not self._queue.empty():
                chunks.append(self._queue.get_nowait())
            if chunks:
                msg = "".join(chunks)
                self.widget.configure(state="normal")
                self.widget.insert("end", msg, (self.tag,))
                self.widget.see("end")
                if self.max_lines:
                    line_count = int(self.widget.index("end-1c").split(".")[0])
                    if line_count > self.max_lines:
                        self.widget.delete("1.0", f"{line_count - self.max_lines}.0")
                self.widget.configure(state="disabled")
        finally:
            self._flush_scheduled = False
            if not self._queue.empty():
                try:
                    self._flush_scheduled = True
                    self.widget.after(100, self._flush_queue)
                except Exception:
                    self._flush_scheduled = False

    def flush(self):
        return None

    def isatty(self):
        return False

    @staticmethod
    def _strip_ansi(text):
        import re

        ansi = re.compile(r"\x1b\[[0-9;]*[mK]")
        return ansi.sub("", text)
