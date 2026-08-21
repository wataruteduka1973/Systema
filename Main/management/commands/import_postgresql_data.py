"""Import a verified SQLite export into an empty PostgreSQL schema."""

from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, transaction

from Main.services.data_migration import load_manifest, ownership_anomalies, target_counts


class Command(BaseCommand):
    help = "検証済みfixtureを空のPostgreSQLへ原子的に投入し、件数と所有権を照合します。"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("fixture")

    def handle(self, *args: Any, **options: Any) -> None:
        if connection.vendor != "postgresql":
            raise CommandError("This command must run with DB_ENGINE=postgresql")

        fixture = Path(options["fixture"]).resolve()
        if not fixture.is_file():
            raise CommandError(f"Fixture not found: {fixture}")
        try:
            manifest = load_manifest(fixture)
        except (OSError, ValueError) as error:
            raise CommandError(str(error)) from error

        expected = manifest.get("included")
        if not isinstance(expected, dict):
            raise CommandError("Manifest does not contain included counts")
        before = target_counts()
        if any(before.values()):
            raise CommandError(f"PostgreSQL target tables are not empty: {before}")

        with transaction.atomic():
            call_command("loaddata", str(fixture), verbosity=1)
            actual = target_counts()
            if actual != expected:
                raise CommandError(
                    f"Imported counts do not match: expected={expected}, actual={actual}"
                )
            anomalies = ownership_anomalies()
            if any(anomalies.values()):
                raise CommandError(f"Ownership or relation anomalies detected: {anomalies}")
            self._reset_sequences()

        self.stdout.write(f"imported: {actual}")
        self.stdout.write(f"ownership anomalies: {anomalies}")
        self.stdout.write(self.style.SUCCESS("PostgreSQL data import completed."))

    def _reset_sequences(self) -> None:
        models = [
            model
            for app_label in ("auth", "Main")
            for model in apps.get_app_config(app_label).get_models()
        ]
        statements = connection.ops.sequence_reset_sql(no_style(), models)
        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)
