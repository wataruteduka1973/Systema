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
