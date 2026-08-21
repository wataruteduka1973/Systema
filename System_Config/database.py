"""Environment-backed Django database configuration."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from django.core.exceptions import ImproperlyConfigured


def build_database_config(base_dir: Path, environ: Mapping[str, str]) -> dict[str, dict[str, Any]]:
    engine = environ.get("DB_ENGINE", "sqlite").strip().lower()
    if engine == "sqlite":
        name = environ.get("DB_NAME", "").strip()
        return {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": Path(name) if name else base_dir / "db.sqlite3",
            }
        }
    if engine != "postgresql":
        raise ImproperlyConfigured("DB_ENGINE must be either 'sqlite' or 'postgresql'")

    required = ("DB_NAME", "DB_USER", "DB_PASSWORD")
    missing = [key for key in required if not environ.get(key, "").strip()]
    if missing:
        raise ImproperlyConfigured(
            "PostgreSQL requires the following environment variables: " + ", ".join(missing)
        )

    port = environ.get("DB_PORT", "5432").strip()
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise ImproperlyConfigured("DB_PORT must be an integer between 1 and 65535")

    connection_age = environ.get("DB_CONN_MAX_AGE", "60").strip()
    if not connection_age.isdigit():
        raise ImproperlyConfigured("DB_CONN_MAX_AGE must be a non-negative integer")

    options: dict[str, str] = {}
    sslmode = environ.get("DB_SSLMODE", "prefer").strip()
    if sslmode:
        options["sslmode"] = sslmode

    return {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": environ["DB_NAME"].strip(),
            "USER": environ["DB_USER"].strip(),
            "PASSWORD": environ["DB_PASSWORD"],
            "HOST": environ.get("DB_HOST", "localhost").strip() or "localhost",
            "PORT": port,
            "CONN_MAX_AGE": int(connection_age),
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": options,
        }
    }
