"""Run the hourly alert scheduler in the foreground, as its own process.

Used by the Linux container deployment (ADR 0007): web workers do not start the in-process timer
(SYSTEMA_ALERT_SCHEDULER=false), and one dedicated process runs it instead. SIGTERM/SIGINT stop the
loop after the current run_alerts child finishes; the job lock still prevents overlapping runs.
"""

from __future__ import annotations

import signal
from typing import Any

from django.core.management.base import BaseCommand

from Main.services.alert_scheduler import configured_scheduler


class Command(BaseCommand):
    help = "Run the alert scheduler in the foreground until stopped."

    def handle(self, *args: Any, **options: Any) -> None:
        scheduler = configured_scheduler()

        def stop(signum: int, frame: Any) -> None:
            scheduler.stop()

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        scheduler.run_forever()
        self.stdout.write("alert scheduler stopped")
