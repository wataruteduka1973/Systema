"""SQLiteからPostgreSQLへ移す所有権付きデータの選別と検証。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import serializers
from django.db.models import Q, QuerySet

from Main.models.errorlog import ErrorLog
from Main.models.scraping import scraping
from Main.models.searchrun import SearchRun
from Main.models.searchwordlog import searchwordlog
from Main.models.watchitem import WatchItem

MIGRATION_FORMAT_VERSION = 1


def selected_querysets() -> tuple[QuerySet[Any], ...]:
    """依存順に、通常移行へ含めるレコードだけを返す。"""
    user_model = get_user_model()
    valid_owner = Q(user__isnull=False) | ~Q(session_key="")
    return (
        Group.objects.order_by("pk"),
        user_model.objects.order_by("pk"),
        SearchRun.objects.filter(valid_owner).order_by("pk"),
        scraping.objects.filter(search_run__isnull=False).order_by("pk"),
        searchwordlog.objects.filter(valid_owner).order_by("pk"),
        WatchItem.objects.filter(valid_owner).order_by("pk"),
    )


def selected_objects() -> Iterable[Any]:
    for queryset in selected_querysets():
        yield from queryset.iterator()


def migration_counts() -> dict[str, int]:
    valid_owner = Q(user__isnull=False) | ~Q(session_key="")
    return {
        "groups": Group.objects.count(),
        "users": get_user_model().objects.count(),
        "search_runs": SearchRun.objects.filter(valid_owner).count(),
        "items": scraping.objects.filter(search_run__isnull=False).count(),
        "search_words": searchwordlog.objects.filter(valid_owner).count(),
        "watch_items": WatchItem.objects.filter(valid_owner).count(),
        "error_logs": 0,
    }


def excluded_counts() -> dict[str, int]:
    return {
        "ownerless_search_runs": SearchRun.objects.filter(
            user__isnull=True, session_key=""
        ).count(),
        "legacy_unlinked_items": scraping.objects.filter(search_run__isnull=True).count(),
        "ownerless_search_words": searchwordlog.objects.filter(
            user__isnull=True, session_key=""
        ).count(),
        "ownerless_watch_items": WatchItem.objects.filter(
            user__isnull=True, session_key=""
        ).count(),
        "error_logs": ErrorLog.objects.count(),
    }


def serialize_selected_data(output: Path) -> None:
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        serializers.serialize(
            "json",
            selected_objects(),
            stream=stream,
            indent=2,
            use_natural_foreign_keys=True,
            use_natural_primary_keys=True,
        )


def write_manifest(
    output: Path,
    source_database: Path,
    source_hash: str,
    counts: dict[str, int],
    excluded: dict[str, int],
) -> Path:
    manifest_path = manifest_for(output)
    payload = {
        "format_version": MIGRATION_FORMAT_VERSION,
        "source_database": str(source_database),
        "source_sha256": source_hash,
        "fixture_sha256": sha256_file(output),
        "included": counts,
        "excluded": excluded,
    }
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest_path


def load_manifest(fixture: Path) -> dict[str, Any]:
    manifest_path = manifest_for(fixture)
    if not manifest_path.is_file():
        raise ValueError(f"Manifest not found: {manifest_path}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("format_version") != MIGRATION_FORMAT_VERSION:
        raise ValueError("Unsupported migration manifest version")
    if payload.get("fixture_sha256") != sha256_file(fixture):
        raise ValueError("Migration fixture SHA256 does not match the manifest")
    return payload


def manifest_for(fixture: Path) -> Path:
    return fixture.with_suffix(fixture.suffix + ".manifest.json")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def target_counts() -> dict[str, int]:
    return {
        "groups": Group.objects.count(),
        "users": get_user_model().objects.count(),
        "search_runs": SearchRun.objects.count(),
        "items": scraping.objects.count(),
        "search_words": searchwordlog.objects.count(),
        "watch_items": WatchItem.objects.count(),
        "error_logs": ErrorLog.objects.count(),
    }


def ownership_anomalies() -> dict[str, int]:
    invalid_owner = Q(user__isnull=True, session_key="") | (
        Q(user__isnull=False) & ~Q(session_key="")
    )
    return {
        "search_runs": SearchRun.objects.filter(invalid_owner).count(),
        "search_words": searchwordlog.objects.filter(invalid_owner).count(),
        "watch_items": WatchItem.objects.filter(invalid_owner).count(),
        "unlinked_items": scraping.objects.filter(search_run__isnull=True).count(),
    }
