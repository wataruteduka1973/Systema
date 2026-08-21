from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

from System_Config.database import build_database_config


def test_sqlite_is_the_safe_default():
    config = build_database_config(Path("C:/systema"), {})["default"]

    assert config["ENGINE"] == "django.db.backends.sqlite3"
    assert config["NAME"] == Path("C:/systema/db.sqlite3")


def test_postgresql_uses_environment_without_exposing_password():
    config = build_database_config(
        Path("C:/systema"),
        {
            "DB_ENGINE": "postgresql",
            "DB_NAME": "Yahuoku_analyze_DB",
            "DB_USER": "systema_app",
            "DB_PASSWORD": "secret-value",
            "DB_HOST": "localhost",
            "DB_PORT": "5432",
            "DB_SSLMODE": "prefer",
        },
    )["default"]

    assert config["ENGINE"] == "django.db.backends.postgresql"
    assert config["NAME"] == "Yahuoku_analyze_DB"
    assert config["USER"] == "systema_app"
    assert config["PASSWORD"] == "secret-value"
    assert config["PORT"] == "5432"
    assert config["CONN_HEALTH_CHECKS"] is True


@pytest.mark.parametrize(
    "environment",
    [
        {"DB_ENGINE": "mysql"},
        {"DB_ENGINE": "postgresql"},
        {
            "DB_ENGINE": "postgresql",
            "DB_NAME": "db",
            "DB_USER": "user",
            "DB_PASSWORD": "password",
            "DB_PORT": "invalid",
        },
    ],
)
def test_invalid_database_configuration_fails_early(environment):
    with pytest.raises(ImproperlyConfigured):
        build_database_config(Path("C:/systema"), environment)
