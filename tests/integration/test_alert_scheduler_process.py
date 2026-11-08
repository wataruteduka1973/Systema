"""The dedicated scheduler process (container deployment) stops cleanly on SIGTERM."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_run_alert_scheduler_waits_then_stops_on_sigterm(tmp_path):
    environment = {
        **os.environ,
        "DB_ENGINE": "sqlite",
        "SYSTEMA_ALERT_SCHEDULER": "false",
        "PYTHONUNBUFFERED": "1",
    }
    process = subprocess.Popen(
        [sys.executable, "manage.py", "run_alert_scheduler"],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    lines = []
    try:
        # Wait for the loop to start; the first run waits two minutes, so none runs before SIGTERM.
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            line = process.stdout.readline()
            if not line:
                break
            lines.append(line)
            if "alert_scheduler_running" in line:
                break
        assert process.poll() is None, "".join(lines)
        process.send_signal(signal.SIGTERM)
        output, _ = process.communicate(timeout=20)
    finally:
        if process.poll() is None:
            process.kill()
    assert process.returncode == 0, "".join(lines) + output
    assert "alert scheduler stopped" in output
