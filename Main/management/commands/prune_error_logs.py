"""Delete error records older than the configured retention period."""

from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from Main.models.errorlog import ErrorLog


class Command(BaseCommand):
    help = "Delete ErrorLog records older than ERROR_LOG_RETENTION_DAYS."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--days", type=int, default=settings.ERROR_LOG_RETENTION_DAYS)

    def handle(self, *args: Any, **options: Any) -> None:
        days = options["days"]
        if not 1 <= days <= 3650:
            raise CommandError("days must be between 1 and 3650")
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = ErrorLog.objects.filter(timestamp__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f"error_logs_deleted={deleted} retention_days={days}"))
