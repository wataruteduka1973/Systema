"""Settings used only by the automated test suite."""

from .settings import *  # noqa: F403

# Tests render templates directly without running collectstatic. Production keeps
# CompressedManifestStaticFilesStorage through the normal settings module.
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
