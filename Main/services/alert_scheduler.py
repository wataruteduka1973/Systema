"""In-process hourly trigger for ``run_alerts``.

The web server process owns only the timer. Each run is a separate ``manage.py run_alerts``
child process, so a hung run can be killed (hard timeout) without touching request threads,
and the job lock still prevents overlap with manual runs or other server workers.
"""

from __future__ import annotations

import atexit
import logging
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connections

from Main.services.error_logging import persist_error
from Main.services.job_lock import JOB_ALREADY_RUNNING_EXIT_CODE

logger = logging.getLogger("server_logger")

STARTUP_DELAY_SECONDS = 120.0
HARD_TIMEOUT_GRACE_SECONDS = 300
SUMMARY_MAX_LENGTH = 200

SUCCEEDED, SKIPPED, FAILED, TIMED_OUT = "succeeded", "skipped", "failed", "timed_out"


@dataclass(frozen=True)
class SchedulerConfig:
    interval_seconds: int
    max_runtime_seconds: int

    def __post_init__(self) -> None:
        if self.interval_seconds <= 0 or self.max_runtime_seconds <= 0:
            raise ImproperlyConfigured("Alert scheduler interval and runtime must be positive")

    @property
    def hard_timeout_seconds(self) -> int:
        # run_alerts stops cooperatively at max_runtime; the grace covers one in-flight unit.
        return self.max_runtime_seconds + HARD_TIMEOUT_GRACE_SECONDS


def alert_job_command(max_runtime_seconds: int) -> list[str]:
    manage = Path(settings.BASE_DIR) / "manage.py"
    return [
        sys.executable,
        str(manage),
        "run_alerts",
        "--max-runtime-seconds",
        str(max_runtime_seconds),
    ]


def _summary(output: str) -> str:
    lines = [line for line in output.splitlines() if line.startswith("saved_searches_refreshed=")]
    return lines[-1][:SUMMARY_MAX_LENGTH] if lines else "no summary"


def _report_failure(message: str) -> None:
    logger.error("%s", message)
    persist_error(error_code="scheduled_alert_job", message=message, location="run_alerts")


def run_alert_job(command: Sequence[str], *, timeout: float) -> str:
    """Run one job to completion or kill it at ``timeout``; return the outcome label."""
    environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    process = subprocess.Popen(
        list(command),
        cwd=settings.BASE_DIR,
        env=environment,
        stdout=subprocess.PIPE,
        # stderr is inherited: per-search diagnostics appear on the server console as for a
        # manual run, and are not copied into persisted error logs.
        stderr=None,
        encoding="utf-8",
        errors="replace",
    )
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        _report_failure(f"scheduled_alert_job outcome={TIMED_OUT} timeout={timeout:g}s")
        return TIMED_OUT
    if process.returncode == 0:
        logger.info("scheduled_alert_job outcome=%s %s", SUCCEEDED, _summary(output))
        return SUCCEEDED
    if process.returncode == JOB_ALREADY_RUNNING_EXIT_CODE:
        logger.info("scheduled_alert_job outcome=%s reason=already_running", SKIPPED)
        return SKIPPED
    # Only the fixed-format summary is persisted, never free-form command output.
    _report_failure(
        f"scheduled_alert_job outcome={FAILED} exit={process.returncode} {_summary(output)}"
    )
    return FAILED


class AlertScheduler:
    def __init__(
        self,
        config: SchedulerConfig,
        *,
        state_path: Path,
        run: Callable[..., str] = run_alert_job,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.config = config
        self.state_path = state_path
        self._run = run
        self._clock = clock
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # Kept in memory too, so an unwritable state file cannot turn the loop into a busy retry.
        self._last_start: float | None = None

    def wait_seconds(self, *, first: bool) -> float:
        """Time until the next run, measured from the last recorded start across restarts."""
        try:
            recorded: float | None = float(self.state_path.read_text(encoding="ascii"))
        except (OSError, ValueError):
            recorded = None
        starts = [value for value in (recorded, self._last_start) if value is not None]
        last = max(starts) if starts else None
        interval = float(self.config.interval_seconds)
        remaining = 0.0 if last is None else last + interval - self._clock()
        # A start time in the future (clock moved back) never delays more than one interval.
        remaining = min(remaining, interval)
        return max(remaining, STARTUP_DELAY_SECONDS if first else 0.0)

    def run_once(self) -> str:
        # Record the start first so a crashed or killed run is not retried on every restart.
        self._last_start = self._clock()
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(f"{self._last_start:.0f}", encoding="ascii")
            return self._run(
                alert_job_command(self.config.max_runtime_seconds),
                timeout=self.config.hard_timeout_seconds,
            )
        except Exception as error:
            _report_failure(f"scheduled_alert_job outcome=error type={type(error).__name__}")
            return FAILED

    def _loop(self) -> None:
        first = True
        while not self._stop.wait(self.wait_seconds(first=first)):
            first = False
            try:
                self.run_once()
            finally:
                # The scheduler thread's own connection (error logs) must not stay open idle.
                connections.close_all()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="alert-scheduler", daemon=True)
        self._thread.start()
        logger.info(
            "alert_scheduler_started interval=%ss max_runtime=%ss",
            self.config.interval_seconds,
            self.config.max_runtime_seconds,
        )

    def stop(self, timeout: float | None = None) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)


_scheduler: AlertScheduler | None = None
_scheduler_lock = threading.Lock()


def start_alert_scheduler() -> AlertScheduler | None:
    """Start the process-wide scheduler once when ``SYSTEMA_ALERT_SCHEDULER`` is enabled."""
    global _scheduler
    if not settings.ALERT_SCHEDULER_ENABLED:
        return None
    with _scheduler_lock:
        if _scheduler is None:
            config = SchedulerConfig(
                interval_seconds=settings.ALERT_SCHEDULER_INTERVAL_SECONDS,
                max_runtime_seconds=settings.ALERT_SCHEDULER_MAX_RUNTIME_SECONDS,
            )
            scheduler = AlertScheduler(
                config, state_path=Path(settings.BASE_DIR) / ".local" / "alert-scheduler-last-start"
            )
            scheduler.start()
            atexit.register(scheduler.stop, 1.0)
            _scheduler = scheduler
        return _scheduler
