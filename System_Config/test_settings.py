"""Settings used only by the automated test suite."""

import os
import tempfile
from pathlib import Path

from .settings import *  # noqa: F403
from .settings import DATABASES
from .static_storage import build_storages

# Tests render templates directly without running collectstatic. Production keeps
# CompressedManifestStaticFilesStorage through the normal settings module.
STORAGES = build_storages(debug=True)

# An in-memory SQLite test database makes Django's live server share one connection across
# its request threads, so concurrent browser requests in E2E tests fail with InterfaceError.
# A per-process file keeps one connection per thread; PostgreSQL is unaffected.
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    DATABASES["default"]["TEST"] = {
        "NAME": str(Path(tempfile.gettempdir()) / f"systema-test-{os.getpid()}.sqlite3")
    }
