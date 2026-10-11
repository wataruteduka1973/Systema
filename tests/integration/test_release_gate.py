from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from Main.management.commands import check_release


@pytest.fixture
def ready_settings(settings, monkeypatch):
    settings.IS_PRODUCTION = True
    settings.DEBUG = False
    settings.ADMIN_SETUP_ENABLED = False
    settings.ALLOWED_HOSTS = ["systema.example.test"]
    settings.CSRF_TRUSTED_ORIGINS = ["https://systema.example.test"]
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache"}}
    monkeypatch.setattr(check_release, "connection", SimpleNamespace(vendor="postgresql"))
    monkeypatch.setattr(check_release, "run_checks", lambda **kwargs: [])
    executor = Mock()
    executor.migration_plan.return_value = []
    monkeypatch.setattr(check_release, "MigrationExecutor", lambda connection: executor)
    storage = Mock()
    storage.stored_name.side_effect = lambda name: name
    storage.exists.return_value = True
    monkeypatch.setattr(check_release, "staticfiles_storage", storage)
    return executor, storage


def test_local_gate_pass_does_not_claim_remote_readiness(ready_settings):
    output = StringIO()
    call_command("check_release", stdout=output)
    assert "Local release prerequisites passed" in output.getvalue()
    assert "NOT VERIFIED" in output.getvalue()


@pytest.mark.parametrize(
    "key,value",
    [
        ("DEBUG", True),
        ("IS_PRODUCTION", False),
        ("ADMIN_SETUP_ENABLED", True),
        ("ALLOWED_HOSTS", ["*"]),
        ("ALLOWED_HOSTS", []),
        ("CSRF_TRUSTED_ORIGINS", ["http://systema.example.test"]),
        ("EXTERNAL_SEARCH_RATE_LIMIT", 0),
        ("AUTH_LOGIN_ACCOUNT_MAX_FAILURES", 0),
        ("CACHES", {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}),
    ],
)
def test_unsafe_release_settings_fail(ready_settings, settings, key, value):
    setattr(settings, key, value)
    with pytest.raises(CommandError, match="Release prerequisites failed"):
        call_command("check_release", stdout=StringIO())


def test_database_failure_is_safe_and_nonzero(ready_settings):
    executor, _ = ready_settings
    executor.migration_plan.side_effect = RuntimeError("password=private-secret")
    output = StringIO()
    with pytest.raises(CommandError):
        call_command("check_release", stdout=output)
    assert "FAIL database_check" in output.getvalue()
    assert "private-secret" not in output.getvalue()


def test_pending_migrations_and_missing_static_fail(ready_settings):
    executor, storage = ready_settings
    executor.migration_plan.return_value = [("pending", False)]
    storage.exists.return_value = False
    output = StringIO()
    with pytest.raises(CommandError):
        call_command("check_release", stdout=output)
    assert "FAIL migrations" in output.getvalue()
    assert "FAIL static_manifest" in output.getvalue()


def test_production_settings_pass_django_deploy_checks():
    import os
    import secrets
    import subprocess
    import sys

    environment = {
        **os.environ,
        "SYSTEMA_ENV": "production",
        "DJANGO_DEBUG": "false",
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(64),
        "DJANGO_ALLOWED_HOSTS": "systema.example.test",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "https://systema.example.test",
        "DB_ENGINE": "sqlite",
        "DJANGO_SETTINGS_MODULE": "System_Config.settings",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    result = subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
