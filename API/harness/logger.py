"""One log helper for the whole harness: every line starts with the file that did the action."""
from pathlib import Path

PREFIX_WIDTH = 16
_sink = print


def set_sink(fn):
    """Redirect log lines (tests capture them). Returns the previous sink."""
    global _sink
    previous, _sink = _sink, fn
    return previous


def log(file, msg):
    """log(__file__, "message") -> `[loop.py]       message`"""
    _sink(f"[{Path(file).name}]".ljust(PREFIX_WIDTH) + msg)
