"""Django CACHES configuration.

The login and external-search rate limits keep their counters in the default cache, so every web
worker must share one cache in production (Redis or Memcached). Local development keeps the
per-process memory cache.
"""

from __future__ import annotations

from collections.abc import Mapping

from django.core.exceptions import ImproperlyConfigured

LOCAL_MEMORY = "django.core.cache.backends.locmem.LocMemCache"
SHARED_BACKENDS = {
    "redis": "django.core.cache.backends.redis.RedisCache",
    "memcached": "django.core.cache.backends.memcached.PyMemcacheCache",
}


def build_cache_config(environ: Mapping[str, str]) -> dict[str, dict[str, str]]:
    """Return CACHES from DJANGO_CACHE_BACKEND (locmem, redis, memcached) and DJANGO_CACHE_LOCATION."""
    name = environ.get("DJANGO_CACHE_BACKEND", "locmem").strip().lower() or "locmem"
    if name == "locmem":
        return {"default": {"BACKEND": LOCAL_MEMORY}}
    if name not in SHARED_BACKENDS:
        raise ImproperlyConfigured("DJANGO_CACHE_BACKEND must be locmem, redis or memcached")
    location = environ.get("DJANGO_CACHE_LOCATION", "").strip()
    if not location:
        raise ImproperlyConfigured("DJANGO_CACHE_LOCATION is required for a shared cache")
    return {"default": {"BACKEND": SHARED_BACKENDS[name], "LOCATION": location}}
