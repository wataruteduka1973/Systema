"""Export ownership-safe data from the legacy SQLite database."""

from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from Main.services.data_migration import (
    excluded_counts,
    migration_counts,
    serialize_selected_data,
    sha256_file,
    write_manifest,
)


class Command(BaseCommand):
    help = "SQLiteから所有権を確認できるデータだけをPostgreSQL移行用に出力します。"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--output", required=True)
        parser.add_argument("--sqlite-backup", required=True)

    def handle(self, *args: Any, **options: Any) -> None:
        if connection.vendor != "sqlite":
            raise CommandError("This command must run with DB_ENGINE=sqlite")

        source = Path(str(connection.settings_dict["NAME"])).resolve()
        backup = Path(options["sqlite_backup"]).resolve()
        output = Path(options["output"]).resolve()
        manifest = output.with_suffix(output.suffix + ".manifest.json")

        if not source.is_file() or not backup.is_file():
            raise CommandError("SQLite source or backup file does not exist")
        if output.exists() or manifest.exists():
            raise CommandError("Output or manifest already exists; choose a new path")
        if source == output or backup == output:
            raise CommandError("Output must not overwrite the source or backup database")

        source_hash = sha256_file(source)
        if source_hash != sha256_file(backup):
            raise CommandError("SQLite backup SHA256 does not match the active database")

        output.parent.mkdir(parents=True, exist_ok=True)
        with transaction.atomic():
            counts = migration_counts()
            excluded = excluded_counts()
            serialize_selected_data(output)
        manifest_path = write_manifest(output, source, source_hash, counts, excluded)

        self.stdout.write(f"fixture: {output}")
        self.stdout.write(f"manifest: {manifest_path}")
        self.stdout.write(f"included: {counts}")
        self.stdout.write(f"excluded: {excluded}")
        self.stdout.write(self.style.SUCCESS("SQLite migration export completed."))
