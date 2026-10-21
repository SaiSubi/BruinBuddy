"""Background work in the API process (upload processing, memory updates, starter questions).

Runs inline when BB_SYNC_JOBS=1 so tests are deterministic. A job queue is the upgrade if uploads grow
(TECHNICAL.md §18)."""
import logging
import threading

from . import config

log = logging.getLogger("bruinbuddy.jobs")


def _safe(fn, *args) -> None:
    try:
        fn(*args)
    except Exception:  # a failed background job must never take the server down
        log.exception("background job %s failed", getattr(fn, "__name__", fn))


def run(fn, *args) -> None:
    if config.SYNC_JOBS:
        _safe(fn, *args)
    else:
        threading.Thread(target=_safe, args=(fn, *args), daemon=True).start()
