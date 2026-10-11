"""In-process run_alerts scheduler: timing, child-process outcomes, and startup gating."""

import importlib
import sys
import threading
import time

import pytest

from Main.models.errorlog import ErrorLog
from Main.services import alert_scheduler
from Main.services.alert_scheduler import (
    FAILED,
    SKIPPED,
    STARTUP_DELAY_SECONDS,
    SUCCEEDED,
    TIMED_OUT,
    AlertScheduler,
    SchedulerConfig,
    run_alert_job,
)
from Main.services.job_lock import JOB_ALREADY_RUNNING_EXIT_CODE

pytestmark = pytest.mark.django_db

HOUR = SchedulerConfig(interval_seconds=3600, max_runtime_seconds=1800)


def _python(code):
    return [sys.executable, "-c", code]


def _scheduler(tmp_path, *, now=10_000.0, run=None, config=HOUR):
    return AlertScheduler(
        config,
        state_path=tmp_path / ".local" / "last-start",
        run=run or (lambda command, timeout: SUCCEEDED),
        clock=lambda: now,
    )


def test_wait_is_measured_from_the_last_recorded_start(tmp_path):
    scheduler = _scheduler(tmp_path)
    assert scheduler.wait_seconds(first=True) == STARTUP_DELAY_SECONDS
    assert scheduler.wait_seconds(first=False) == 0

    scheduler.state_path.parent.mkdir()
    scheduler.state_path.write_text("9000")  # started 1000s ago
    assert scheduler.wait_seconds(first=True) == 2600
    scheduler.state_path.write_text("1000")  # overdue: still let the server finish starting
    assert scheduler.wait_seconds(first=True) == STARTUP_DELAY_SECONDS
    assert scheduler.wait_seconds(first=False) == 0
    scheduler.state_path.write_text("999999")  # clock moved back
    assert scheduler.wait_seconds(first=False) == 3600
    scheduler.state_path.write_text("garbage")
    assert scheduler.wait_seconds(first=True) == STARTUP_DELAY_SECONDS


def test_run_once_records_start_and_passes_bounded_command(tmp_path, settings):
    settings.BASE_DIR = tmp_path
    calls = []
    scheduler = _scheduler(tmp_path, run=lambda command, timeout: calls.append((command, timeout)))

    scheduler.run_once()

    assert scheduler.state_path.read_text() == "10000"
    command, timeout = calls[0]
    assert command[1:] == [
        str(tmp_path / "manage.py"),
        "run_alerts",
        "--max-runtime-seconds",
        "1800",
    ]
    assert timeout == 1800 + alert_scheduler.HARD_TIMEOUT_GRACE_SECONDS


def test_run_once_reports_an_unexpected_launch_error(tmp_path):
    def fail(command, timeout):
        raise OSError("private path detail")

    assert _scheduler(tmp_path, run=fail).run_once() == FAILED
    log = ErrorLog.objects.get()
    assert log.error_code == "scheduled_alert_job"
    assert "OSError" in log.error_message
    assert "private" not in log.error_message


def test_unwritable_state_file_still_waits_a_full_interval(tmp_path):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("")
    scheduler = AlertScheduler(
        HOUR,
        state_path=blocker / "last-start",
        run=lambda command, timeout: pytest.fail("ran without a recorded start"),
        clock=lambda: 10_000.0,
    )

    assert scheduler.run_once() == FAILED
    assert scheduler.wait_seconds(first=False) == 3600


def test_successful_job_logs_summary_without_error_record(caplog):
    code = "print('noise'); print('saved_searches_refreshed=2 failed=0 notifications_created=1')"
    with caplog.at_level("INFO", logger="server_logger"):
        assert run_alert_job(_python(code), timeout=30) == SUCCEEDED
    assert "saved_searches_refreshed=2 failed=0 notifications_created=1" in caplog.text
    assert not ErrorLog.objects.exists()


def test_busy_lock_is_a_skip_not_a_failure():
    code = f"import sys; sys.exit({JOB_ALREADY_RUNNING_EXIT_CODE})"
    assert run_alert_job(_python(code), timeout=30) == SKIPPED
    assert not ErrorLog.objects.exists()


def test_failed_job_persists_only_the_summary():
    code = (
        "import sys; print('private stdout line');"
        "print('saved_searches_refreshed=0 failed=1 notifications_created=0'); sys.exit(1)"
    )
    assert run_alert_job(_python(code), timeout=30) == FAILED
    message = ErrorLog.objects.get().error_message
    assert "exit=1" in message
    assert "failed=1" in message
    assert "private" not in message


def test_hung_job_is_killed_at_the_hard_timeout():
    started = time.monotonic()
    assert run_alert_job(_python("import time; time.sleep(60)"), timeout=0.5) == TIMED_OUT
    assert time.monotonic() - started < 10
    assert "timed_out" in ErrorLog.objects.get().error_message


def test_loop_runs_back_to_back_after_startup_and_stops(tmp_path, monkeypatch):
    monkeypatch.setattr(alert_scheduler, "STARTUP_DELAY_SECONDS", 0.0)
    ran = threading.Event()
    calls = []

    def run(command, timeout):
        calls.append(command)
        if len(calls) == 2:
            ran.set()
        return SUCCEEDED

    # A recorded start long ago makes every wait zero, so two runs happen immediately.
    scheduler = AlertScheduler(
        SchedulerConfig(interval_seconds=1, max_runtime_seconds=1),
        state_path=tmp_path / "last-start",
        run=run,
        clock=lambda: 0.0 if not calls else -10.0,
    )
    scheduler.start()
    try:
        assert ran.wait(10)
    finally:
        scheduler.stop(5)
    assert not scheduler._thread.is_alive()


@pytest.mark.parametrize("interval, runtime", [(0, 1), (1, 0)])
def test_config_rejects_non_positive_values(interval, runtime):
    with pytest.raises(Exception, match="must be positive"):
        SchedulerConfig(interval_seconds=interval, max_runtime_seconds=runtime)


@pytest.fixture
def fresh_scheduler(monkeypatch):
    monkeypatch.setattr(alert_scheduler, "_scheduler", None)
    started = []
    monkeypatch.setattr(AlertScheduler, "start", lambda self: started.append(self))
    return started


def test_disabled_scheduler_is_not_started(settings, fresh_scheduler):
    settings.ALERT_SCHEDULER_ENABLED = False
    assert alert_scheduler.start_alert_scheduler() is None
    assert fresh_scheduler == []


def test_enabled_scheduler_starts_once_per_process(settings, tmp_path, fresh_scheduler):
    settings.ALERT_SCHEDULER_ENABLED = True
    settings.BASE_DIR = tmp_path
    first = alert_scheduler.start_alert_scheduler()
    assert alert_scheduler.start_alert_scheduler() is first
    assert fresh_scheduler == [first]
    assert first.state_path == tmp_path / ".local" / "alert-scheduler-last-start"


def test_server_entrypoint_starts_the_scheduler(settings, fresh_scheduler):
    settings.ALERT_SCHEDULER_ENABLED = True
    import System_Config.wsgi as wsgi

    importlib.reload(wsgi)
    assert len(fresh_scheduler) == 1
