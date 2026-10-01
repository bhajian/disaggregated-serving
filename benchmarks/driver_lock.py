"""Single-driver lock and append-only evidence for in-cluster benchmark drivers.

The 8K/128K study once had a second driver start while a run was in progress. It asked
the workers to flush their caches (they refused because requests were active) and
overwrote the first driver's cache-clear log. These helpers make that impossible:
acquire() takes an exclusive lock for the whole driver process, and append_evidence()
records every cache-flush acknowledgement as a timestamped JSON line that is only ever
appended, never truncated.
"""
import datetime
import fcntl
import json
import os
from pathlib import Path

EVIDENCE = 'cache-flush-evidence.jsonl'


class DriverBusy(RuntimeError):
    """Another driver already holds the lock in this results directory."""


def acquire(logdir):
    """Hold an exclusive lock on <logdir>/.driver.lock for the life of the process."""
    logdir = Path(logdir)
    logdir.mkdir(parents=True, exist_ok=True)
    handle = open(logdir / '.driver.lock', 'a')
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise DriverBusy(f'another benchmark driver holds {logdir / ".driver.lock"}') from None
    handle.seek(0); handle.truncate(); handle.write(f'{os.getpid()}\n'); handle.flush()
    return handle


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def append_evidence(logdir, record):
    """Append one timestamped JSON record to <logdir>/cache-flush-evidence.jsonl."""
    path = Path(logdir) / EVIDENCE
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({'utc': now(), 'pid': os.getpid(), **record}, sort_keys=True) + '\n'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line.encode())
    finally:
        os.close(fd)
    return path
