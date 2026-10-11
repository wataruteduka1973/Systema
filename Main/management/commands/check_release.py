"""Read-only release diagnostics; never infer remote deployment readiness."""

from typing import Any

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.checks import WARNING, run_checks
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = "Check local production prerequisites without changing data or revealing secrets."
    requires_system_checks: list[str] = []

    def handle(self, *args: Any, **options: Any) -> None:
        failures = []
        checks = {
            "production_mode": settings.IS_PRODUCTION,
            "debug_disabled": not settings.DEBUG,
            "admin_setup_disabled": not settings.ADMIN_SETUP_ENABLED,
            "explicit_hosts": bool(settings.ALLOWED_HOSTS)
            and all(
                host not in {"*", "localhost", "127.0.0.1", "[::1]"} and not host.startswith(".")
                for host in settings.ALLOWED_HOSTS
            ),
            "https_origins": bool(settings.CSRF_TRUSTED_ORIGINS)
            and all(
                origin.startswith("https://") and "*" not in origin
                for origin in settings.CSRF_TRUSTED_ORIGINS
            ),
            "postgresql": connection.vendor == "postgresql",
            "search_throttle_enabled": settings.EXTERNAL_SEARCH_RATE_LIMIT > 0
            and settings.EXTERNAL_SEARCH_RATE_WINDOW_SECONDS > 0,
            "login_throttle_enabled": settings.AUTH_LOGIN_ACCOUNT_MAX_FAILURES > 0
            and settings.AUTH_LOGIN_IP_MAX_FAILURES > 0
            and settings.AUTH_LOGIN_WINDOW_SECONDS > 0,
            "shared_rate_limit_cache": settings.CACHES["default"]["BACKEND"]
            in {
                "django.core.cache.backends.redis.RedisCache",
                "django.core.cache.backends.memcached.PyMemcacheCache",
                "django.core.cache.backends.memcached.PyLibMCCache",
            },
        }
        for name, passed in checks.items():
            self.stdout.write(f"{'PASS' if passed else 'FAIL'} {name}")
            if not passed:
                failures.append(name)
        # Only fixed check IDs are emitted: check messages can contain configuration values.
        for issue in run_checks(include_deployment_checks=True):
            if issue.level >= WARNING:
                failures.append("django_deployment_check")
                self.stdout.write(f"FAIL django_deployment_check {issue.id}")
        try:
            executor = MigrationExecutor(connection)
            executor.loader.check_consistent_history(connection)
            pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
            if pending:
                failures.append("migrations")
            self.stdout.write(f"{'FAIL' if pending else 'PASS'} migrations")
        except Exception:
            failures.append("database_check")
            self.stdout.write("FAIL database_check")
        try:
            for asset in ("JS/ClientErrors.js", "JS/Notifications.js", "JS/AlertRules.js"):
                stored = staticfiles_storage.stored_name(asset)
                if not staticfiles_storage.exists(stored):
                    raise ValueError("missing asset")
            self.stdout.write("PASS static_manifest")
        except Exception:
            failures.append("static_manifest")
            self.stdout.write("FAIL static_manifest")
        self.stdout.write(
            "NOT VERIFIED: HTTPS/proxy, shared-cache connectivity, backup restore, scheduler, production browser"
        )
        if failures:
            raise CommandError(f"Release prerequisites failed ({len(failures)} checks).")
        self.stdout.write(
            self.style.SUCCESS(
                "Local release prerequisites passed; external checks remain required."
            )
        )
