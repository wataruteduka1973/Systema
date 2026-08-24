import json

import pytest
from django.conf import settings
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "view_name",
    ["yahuoku_history", "Deep_Analysis", "Deep_Analysis_now"],
)
def test_mutating_pages_issue_csrf_cookie(client, view_name):
    response = client.get(reverse(view_name))

    assert response.status_code == 200
    assert "csrftoken" in response.cookies


@pytest.mark.parametrize(
    ("method", "view_name", "kwargs"),
    [
        ("post", "update_market_data", {}),
        ("delete", "delete_market_data", {}),
        ("post", "watchlist", {}),
        ("delete", "watchlist_item", {"item_id": 1}),
    ],
)
def test_mutating_api_rejects_missing_csrf_token(client, method, view_name, kwargs):
    csrf_client = client_class_with_csrf(client)
    response = getattr(csrf_client, method)(reverse(view_name, kwargs=kwargs))

    assert response.status_code == 403


def test_watchlist_accepts_csrf_header(client):
    csrf_client = client_class_with_csrf(client)
    csrf_client.get(reverse("Deep_Analysis_now"))
    token = csrf_client.cookies["csrftoken"].value

    response = csrf_client.post(
        reverse("watchlist"),
        data=json.dumps({"url": "https://example.com/not-yahoo"}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )

    assert response.status_code == 400
    assert response.json()["error"]


def test_security_headers_and_session_hardening_are_enabled(client):
    response = client.get(reverse("login"))

    assert "default-src 'self'" in response["Content-Security-Policy"]
    assert "object-src 'none'" in response["Content-Security-Policy"]
    assert response["X-Frame-Options"] == "DENY"
    assert settings.SESSION_COOKIE_HTTPONLY is True
    assert settings.SESSION_EXPIRE_AT_BROWSER_CLOSE is True
    assert settings.SESSION_COOKIE_AGE == 28800


def client_class_with_csrf(client):
    return client.__class__(enforce_csrf_checks=True)
