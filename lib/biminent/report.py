# -*- coding: utf-8 -*-
"""Standard error reporting for Biminent tools.

When something goes wrong we want the same behaviour everywhere:
  - the FULL traceback printed to the pyRevit output (so it's diagnosable), and
  - a short, friendly one-liner for the tool's status line (so the user isn't
    hit with a raw stack trace).

Two ways to use it:

    # 1. wrap an action (preferred) - errors are caught, logged, and shown:
    with self.report_errors("Rename"):
        ... do the work ...

    # 2. inside an except block, when you want to keep going:
    try:
        ...
    except Exception:
        msg = report.log_traceback("Link DWGs")   # -> short message string
"""
import os
import sys
import traceback
from datetime import datetime

from pyrevit import script

# Persistent error log - the reliable record. The pyRevit output window can fail
# to surface (e.g. from a modal dialog, or if get_output() throws under some
# engines), so we always also append the full traceback to this file, which
# works on every Revit version and engine.
ERROR_LOG = os.path.join(
    os.environ.get("APPDATA") or os.path.expanduser("~"),
    "Biminent", "Tools", "biminent_errors.log")


def _append_to_logfile(title, tb_text):
    try:
        folder = os.path.dirname(ERROR_LOG)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        with open(ERROR_LOG, "a") as handle:
            handle.write("\n=== {} | {} ===\n{}\n".format(
                datetime.now().isoformat(), title, tb_text))
    except Exception:
        pass  # reporting must never raise


def log_traceback(title):
    """Record the current exception's traceback (to the persistent log file and,
    best-effort, the pyRevit output) and return a short one-line message. Call
    from inside `except`."""
    exc_type, exc_value = sys.exc_info()[:2]
    short = "{}: {}".format(getattr(exc_type, "__name__", "Error"), exc_value)
    tb_text = traceback.format_exc()
    _append_to_logfile(title, tb_text)
    try:
        out = script.get_output()
        out.print_md("### {} - something went wrong".format(title))
        out.print_md("```\n{}\n```".format(tb_text))
        try:
            out.show()  # bring the output window to the front of the modal dialog
        except Exception:
            pass
    except Exception:
        pass  # reporting must never raise
    return short


class guard(object):
    """Context manager: catches any exception inside the block, logs the full
    traceback, and (optionally) pushes a short message to a status callback.
    Swallows the exception so the tool window stays alive."""

    def __init__(self, title, on_status=None):
        self.title = title
        self.on_status = on_status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if exc_type is None:
            return False
        short = log_traceback(self.title)
        if self.on_status is not None:
            try:
                self.on_status(short)
            except Exception:
                pass
        return True  # handled - don't propagate
