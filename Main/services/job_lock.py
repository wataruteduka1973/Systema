"""Nonblocking alert-job ownership for PostgreSQL and single-host local SQLite."""

import importlib
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from django.conf import settings
from django.db import connection

LOCK_KEY = 739_245_901


class JobAlreadyRunning(RuntimeError):
    pass


@contextmanager
def alert_job_lock() -> Iterator[Callable[[], None]]:
    if connection.vendor == "postgresql":
        lock_connection = connection.copy(alias="alert_job_lock")
        try:
            with lock_connection.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_lock(%s), pg_backend_pid()", [LOCK_KEY])
                acquired, process_id = cursor.fetchone()
            if not acquired:
                raise JobAlreadyRunning("Alert job is already running")

            def check_ownership() -> None:
                with lock_connection.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    if cursor.fetchone()[0] != process_id:
                        raise RuntimeError("Alert job lock connection changed")

            yield check_ownership
        finally:
            # Session close releases the lock, including exception and normal exits.
            lock_connection.close()
        return
    if connection.vendor != "sqlite" or settings.IS_PRODUCTION:
        raise RuntimeError("Scheduled jobs require PostgreSQL in production")
    # Stable file: do not unlink after unlock (another process may hold the inode).
    path = settings.BASE_DIR / ".local" / "run-alerts.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        module: Any = importlib.import_module("msvcrt" if os.name == "nt" else "fcntl")
        if os.name == "nt":
            stream.seek(0, 2)
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
        try:
            if os.name == "nt":
                module.locking(stream.fileno(), module.LK_NBLCK, 1)
            else:
                module.flock(stream.fileno(), module.LOCK_EX | module.LOCK_NB)
        except OSError:
            raise JobAlreadyRunning("Alert job is already running") from None
        try:
            yield lambda: None
        finally:
            if os.name == "nt":
                stream.seek(0)
                module.locking(stream.fileno(), module.LK_UNLCK, 1)
            else:
                module.flock(stream.fileno(), module.LOCK_UN)
