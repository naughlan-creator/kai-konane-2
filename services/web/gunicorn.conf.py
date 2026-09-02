"""gunicorn configuration.

Exists for one reason: prometheus_client's multiprocess mode needs lifecycle
hooks that only the master process can provide.

Each worker writes its counters into memory-mapped files under
PROMETHEUS_MULTIPROC_DIR, and a scrape sums them. Two failure modes follow, and
neither raises anything:

  Stale files. A worker that dies leaves its files behind. Without
  mark_process_dead they are summed in forever, so counters from processes that
  no longer exist inflate every reading -- and the drift only ever grows.

  Stale directory. Files surviving a container restart are added to a fresh
  run's numbers, so request totals start the day somewhere above zero and no
  rate() over them is trustworthy.
"""
import os
import shutil


def on_starting(server):
    """Master start: clear the directory before any worker writes to it."""
    path = os.environ.get('PROMETHEUS_MULTIPROC_DIR')
    if not path:
        return
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path, exist_ok=True)


def child_exit(server, worker):
    """A worker died: drop its files so its counters stop being summed.

    child_exit, not worker_exit -- this must run in the MASTER, which is the
    only process that outlives the worker and can clean up after it.
    """
    if not os.environ.get('PROMETHEUS_MULTIPROC_DIR'):
        return
    from prometheus_client import multiprocess
    multiprocess.mark_process_dead(worker.pid)