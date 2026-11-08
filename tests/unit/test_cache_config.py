import pytest
from django.core.exceptions import ImproperlyConfigured

from System_Config.cache import build_cache_config


def test_local_development_uses_the_process_memory_cache():
    assert build_cache_config({}) == {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }


@pytest.mark.parametrize(
    ("name", "backend"),
    [
        ("redis", "django.core.cache.backends.redis.RedisCache"),
        ("Memcached", "django.core.cache.backends.memcached.PyMemcacheCache"),
    ],
)
def test_shared_caches_need_a_location(name, backend):
    config = build_cache_config(
        {"DJANGO_CACHE_BACKEND": name, "DJANGO_CACHE_LOCATION": "redis://cache:6379/0"}
    )

    assert config == {"default": {"BACKEND": backend, "LOCATION": "redis://cache:6379/0"}}
    with pytest.raises(ImproperlyConfigured, match="LOCATION"):
        build_cache_config({"DJANGO_CACHE_BACKEND": name})


def test_an_unknown_backend_is_rejected():
    with pytest.raises(ImproperlyConfigured, match="locmem, redis or memcached"):
        build_cache_config({"DJANGO_CACHE_BACKEND": "database"})
