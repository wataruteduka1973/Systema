"""Django STORAGES configuration for uploaded and static files."""

from __future__ import annotations

FILE_SYSTEM_STORAGE = "django.core.files.storage.FileSystemStorage"
PLAIN_STATIC_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
PRODUCTION_STATIC_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


def build_storages(debug: bool) -> dict[str, dict[str, str]]:
    """Return STORAGES; production serves hashed, compressed static files.

    Django 5.1 removed STATICFILES_STORAGE, so the static backend must be set here.
    """
    return {
        "default": {"BACKEND": FILE_SYSTEM_STORAGE},
        "staticfiles": {"BACKEND": PLAIN_STATIC_STORAGE if debug else PRODUCTION_STATIC_STORAGE},
    }
