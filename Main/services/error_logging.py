"""Safe persistence for server and browser error events."""

import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from Main.models.errorlog import ErrorLog

logger = logging.getLogger("error_logger")


def prune_expired_error_logs() -> None:
    today = timezone.localdate().isoformat()
    cache_key = f"error-log-retention:{today}"
    if not cache.add(cache_key, 1, timeout=86_400):
        return
    try:
        cutoff = timezone.now() - timedelta(days=settings.ERROR_LOG_RETENTION_DAYS)
        ErrorLog.objects.filter(timestamp__lt=cutoff).delete()
    except Exception:
        cache.delete(cache_key)
        logger.error("error_log_retention_failed")


def persist_error(
    *, error_code: str, message: str, location: str = "", line_number: int | None = None
) -> bool:
    prune_expired_error_logs()
    try:
        with transaction.atomic():
            ErrorLog.objects.create(
                error_code=error_code[:50],
                error_message=message,
                file_path=location[:255],
                line_number=line_number,
            )
        return True
    except Exception:
        logger.error("error_log_persistence_failed code=%s", error_code[:50])
        return False


def persist_client_error(request: Any, kind: str) -> bool:
    request_id = getattr(request, "error_request_id", "unavailable")
    route = getattr(getattr(request, "resolver_match", None), "view_name", None) or "unresolved"
    message = f"request_id={request_id} source=browser kind={kind} route={route}"
    logger.error("%s", message)
    return persist_error(error_code="client_error", message=message, location=route)
