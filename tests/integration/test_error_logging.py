from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.core.management import call_command
from django.db import DatabaseError
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from django.utils import timezone

from Main.middleware.error_logging_middleware import ErrorLoggingMiddleware
from Main.models.errorlog import ErrorLog

pytestmark = pytest.mark.django_db


def test_http_failure_has_correlation_without_request_secrets():
    request = RequestFactory().get("/private-token?password=secret")
    middleware = ErrorLoggingMiddleware(lambda request: HttpResponse(status=503))
    response = middleware(request)
    record = ErrorLog.objects.get()
    assert response["X-Request-ID"] in record.error_message
    assert "private-token" not in record.error_message + record.file_path
    assert "secret" not in record.error_message


def test_exception_is_recorded_once_without_exception_text():
    def view(request):
        try:
            raise ValueError("password=secret")
        except ValueError as error:
            middleware.process_exception(request, error)
        return HttpResponse(status=500)

    middleware = ErrorLoggingMiddleware(view)
    response = middleware(RequestFactory().get("/"))
    record = ErrorLog.objects.get()
    assert "ValueError" in record.error_message
    assert "secret" not in record.error_message
    assert "frames=" in record.error_message
    assert response.status_code == 500


def test_database_logging_failure_preserves_response(monkeypatch):
    monkeypatch.setattr(ErrorLog.objects, "create", Mock(side_effect=DatabaseError("secret")))
    response = ErrorLoggingMiddleware(lambda request: HttpResponse(status=502))(
        RequestFactory().get("/")
    )
    assert response.status_code == 502
    assert ErrorLog.objects.count() == 0


def test_csrf_rejection_is_captured_before_view():
    from django.test import Client

    response = Client(enforce_csrf_checks=True).post("/accounts/login/", {})
    assert response.status_code == 403
    assert ErrorLog.objects.filter(error_code="403").count() == 1


def test_success_is_not_an_error():
    response = ErrorLoggingMiddleware(lambda request: HttpResponse())(RequestFactory().get("/"))
    assert response.status_code == 200
    assert not ErrorLog.objects.exists()


@override_settings(CLIENT_ERROR_RATE_LIMIT=2, CLIENT_ERROR_RATE_WINDOW_SECONDS=60)
def test_browser_error_accepts_kind_only_and_is_rate_limited(client):
    from django.core.cache import cache

    cache.clear()
    url = "/taskle/api/v1/client-errors"
    assert client.post(url, {"kind": "error"}, content_type="application/json").status_code == 204
    assert (
        client.post(url, {"kind": "resource"}, content_type="application/json").status_code == 204
    )
    assert (
        client.post(
            url, {"kind": "unhandledrejection"}, content_type="application/json"
        ).status_code
        == 204
    )
    assert (
        client.post(
            url, {"kind": "error", "message": "password=secret"}, content_type="application/json"
        ).status_code
        == 204
    )
    assert ErrorLog.objects.filter(error_code="client_error").count() == 2
    assert "secret" not in "".join(ErrorLog.objects.values_list("error_message", flat=True))


def test_prune_error_logs_respects_retention():
    old = ErrorLog.objects.create(error_code="old", error_message="old")
    recent = ErrorLog.objects.create(error_code="recent", error_message="recent")
    ErrorLog.objects.filter(pk=old.pk).update(timestamp=timezone.now() - timedelta(days=91))
    call_command("prune_error_logs", days=90)
    assert not ErrorLog.objects.filter(pk=old.pk).exists()
    assert ErrorLog.objects.filter(pk=recent.pk).exists()


@override_settings(ERROR_LOG_RETENTION_DAYS=90)
def test_error_write_prunes_expired_records_once_daily():
    from django.core.cache import cache

    cache.clear()
    old = ErrorLog.objects.create(error_code="old", error_message="old")
    ErrorLog.objects.filter(pk=old.pk).update(timestamp=timezone.now() - timedelta(days=91))
    response = ErrorLoggingMiddleware(lambda request: HttpResponse(status=500))(
        RequestFactory().get("/")
    )
    assert response.status_code == 500
    assert not ErrorLog.objects.filter(pk=old.pk).exists()
    assert ErrorLog.objects.filter(error_code="500").count() == 1
