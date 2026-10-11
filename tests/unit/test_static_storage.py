from System_Config.static_storage import (
    PLAIN_STATIC_STORAGE,
    PRODUCTION_STATIC_STORAGE,
    build_storages,
)


def test_production_uses_compressed_manifest_static_storage():
    storages = build_storages(debug=False)

    assert storages["staticfiles"]["BACKEND"] == PRODUCTION_STATIC_STORAGE
    assert storages["default"]["BACKEND"] == "django.core.files.storage.FileSystemStorage"


def test_debug_uses_plain_static_storage_without_collectstatic():
    assert build_storages(debug=True)["staticfiles"]["BACKEND"] == PLAIN_STATIC_STORAGE


def test_runserver_leaves_static_files_to_whitenoise():
    """run_systema.bat uses `runserver --insecure`; Django's own static handler only knows
    unhashed names, so with manifest storage it answered 404 for every asset."""
    from django.conf import settings
    from django.core.management import get_commands

    apps = list(settings.INSTALLED_APPS)

    assert get_commands()["runserver"] == "whitenoise.runserver_nostatic"
    assert apps.index("whitenoise.runserver_nostatic") < apps.index("django.contrib.staticfiles")
