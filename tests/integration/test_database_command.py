from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection

pytestmark = pytest.mark.django_db


def test_check_database_verifies_standard_and_systema_tables():
    output = StringIO()

    call_command(
        "check_database",
        require_standard=True,
        require_systema=True,
        stdout=output,
    )

    result = output.getvalue()
    assert f"backend: {connection.vendor}" in result
    assert "Django標準 tables: OK" in result
    assert "Systema tables: OK" in result
    assert "Database verification passed." in result
