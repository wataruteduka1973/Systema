"""Verify the active database connection and expected schema."""

from __future__ import annotations

from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

STANDARD_TABLES = {
    "django_migrations",
    "django_content_type",
    "auth_permission",
    "auth_group",
    "auth_user",
    "django_admin_log",
    "django_session",
}
SYSTEMA_TABLES = {
    "Main_errorlog",
    "Main_searchrun",
    "Main_scraping",
    "Main_searchwordlog",
    "Main_watchitem",
}


class Command(BaseCommand):
    help = "接続中DBとDjango/Systemaテーブルの存在を読み取り専用で確認します。"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--require-standard",
            action="store_true",
            help="Django標準テーブルが不足している場合に失敗します。",
        )
        parser.add_argument(
            "--require-systema",
            action="store_true",
            help="Systema固有テーブルが不足している場合に失敗します。",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            connection.ensure_connection()
            tables = set(connection.introspection.table_names())
            version = self._database_version()
        except Exception as error:
            raise CommandError(
                "データベースへ接続できませんでした。設定と稼働状態を確認してください。"
            ) from error

        database_name = str(connection.settings_dict.get("NAME", ""))
        self.stdout.write(f"backend: {connection.vendor}")
        self.stdout.write(f"database: {database_name}")
        self.stdout.write(f"server: {version}")
        self.stdout.write(f"tables: {len(tables)}")

        if options["require_standard"]:
            self._require_tables("Django標準", STANDARD_TABLES, tables)
        if options["require_systema"]:
            self._require_tables("Systema", SYSTEMA_TABLES, tables)
        self.stdout.write(self.style.SUCCESS("Database verification passed."))

    def _database_version(self) -> str:
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SHOW server_version")
                return str(cursor.fetchone()[0])
        return (
            str(connection.Database.sqlite_version) if connection.vendor == "sqlite" else "unknown"
        )

    def _require_tables(self, label: str, required: set[str], actual: set[str]) -> None:
        missing = sorted(required - actual)
        if missing:
            raise CommandError(f"{label}テーブルが不足しています: {', '.join(missing)}")
        self.stdout.write(self.style.SUCCESS(f"{label} tables: OK"))
