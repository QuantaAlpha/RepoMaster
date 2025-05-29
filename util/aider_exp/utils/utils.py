import itertools
import os
import git
import platform
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path





def safe_abs_path(res):
    "Gives an abs path, which safely returns a full (not 8.3) windows path"
    res = Path(res).resolve()
    return str(res)


class Spinner:
    unicode_spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    ascii_spinner = ["|", "/", "-", "\\"]

    def __init__(self, text):
        self.text = text
        self.start_time = time.time()
        self.last_update = 0
        self.visible = False
        self.is_tty = sys.stdout.isatty()
        self.tested = False

    def test_charset(self):
        if self.tested:
            return
        self.tested = True
        # Try unicode first, fall back to ascii if needed
        try:
            # Test if we can print unicode characters
            print(self.unicode_spinner[0], end="", flush=True)
            print("\r", end="", flush=True)
            self.spinner_chars = itertools.cycle(self.unicode_spinner)
        except UnicodeEncodeError:
            self.spinner_chars = itertools.cycle(self.ascii_spinner)

    def step(self):
        if not self.is_tty:
            return

        current_time = time.time()
        if not self.visible and current_time - self.start_time >= 0.5:
            self.visible = True
            self._step()
        elif self.visible and current_time - self.last_update >= 0.1:
            self._step()
        self.last_update = current_time

    def _step(self):
        if not self.visible:
            return

        self.test_charset()
        print(f"\r{self.text} {next(self.spinner_chars)}\r{self.text} ", end="", flush=True)

    def end(self):
        if self.visible and self.is_tty:
            print("\r" + " " * (len(self.text) + 3))


def find_common_root(abs_fnames):
    try:
        if len(abs_fnames) == 1:
            return safe_abs_path(os.path.dirname(list(abs_fnames)[0]))
        elif abs_fnames:
            return safe_abs_path(os.path.commonpath(list(abs_fnames)))
    except OSError:
        pass

    try:
        return safe_abs_path(os.getcwd())
    except FileNotFoundError:
        # Fallback if cwd is deleted
        return "."