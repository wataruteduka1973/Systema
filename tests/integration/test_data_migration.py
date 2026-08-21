import json

import pytest
from django.contrib.auth import get_user_model

from Main.models.errorlog import ErrorLog
from Main.models.scraping import scraping
from Main.models.searchrun import SearchRun
from Main.models.searchwordlog import searchwordlog
from Main.models.watchitem import WatchItem
from Main.services.data_migration import (
    excluded_counts,
    load_manifest,
    migration_counts,
    ownership_anomalies,
    serialize_selected_data,
    sha256_file,
    write_manifest,
)


@pytest.mark.django_db
def test_migration_selection_excludes_unowned_legacy_data(tmp_path):
    user = get_user_model().objects.create_user(username="migration-user")
    user_run = SearchRun.objects.create(user=user, keyword="camera")
    session_run = SearchRun.objects.create(session_key="session-1", keyword="lens")
    SearchRun.objects.create(keyword="ownerless")

    for run in (user_run, session_run):
        scraping.objects.create(
            search_run=run,
            SearchWord=run.keyword,
            SearchDay="2026-08-21",
            Bidding="1",
            EndPrice=1000,
            StartPrice=500,
            Name=run.keyword,
            URL=f"https://example.test/{run.pk}",
        )
    scraping.objects.create(
        SearchWord="legacy",
        SearchDay="2020-01-01",
        Bidding="0",
        EndPrice=0,
        StartPrice=0,
        Name="legacy",
        URL="https://example.test/legacy",
    )
    searchwordlog.objects.create(user=user, word="camera")
    searchwordlog.objects.create(session_key="session-1", word="lens")
    searchwordlog.objects.create(word="ownerless")
    WatchItem.objects.create(user=user, name="camera", url="https://example.test/watch")
    ErrorLog.objects.create(error_code="legacy", error_message="legacy error")

    assert migration_counts() == {
        "groups": 0,
        "users": 1,
        "search_runs": 2,
        "items": 2,
        "search_words": 2,
        "watch_items": 1,
        "error_logs": 0,
    }
    assert excluded_counts() == {
        "ownerless_search_runs": 1,
        "legacy_unlinked_items": 1,
        "ownerless_search_words": 1,
        "ownerless_watch_items": 0,
        "error_logs": 1,
    }

    fixture = tmp_path / "migration.json"
    serialize_selected_data(fixture)
    records = json.loads(fixture.read_text(encoding="utf-8"))
    models = [record["model"] for record in records]
    assert models.count("auth.user") == 1
    assert models.count("Main.searchrun") == 2
    assert models.count("Main.scraping") == 2
    assert "Main.errorlog" not in models


def test_manifest_detects_fixture_tampering(tmp_path):
    source = tmp_path / "db.sqlite3"
    fixture = tmp_path / "migration.json"
    source.write_bytes(b"sqlite")
    fixture.write_text("[]", encoding="utf-8")
    write_manifest(fixture, source, sha256_file(source), {}, {})

    assert load_manifest(fixture)["fixture_sha256"] == sha256_file(fixture)
    fixture.write_text("[ ]", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA256"):
        load_manifest(fixture)


@pytest.mark.django_db
def test_ownership_anomalies_detects_dual_and_missing_owners():
    user = get_user_model().objects.create_user(username="owner")
    SearchRun.objects.create(user=user, session_key="unexpected", keyword="dual")
    SearchRun.objects.create(keyword="missing")

    assert ownership_anomalies()["search_runs"] == 2
