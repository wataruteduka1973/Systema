from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone

from Main.models.auththrottle import AuthThrottle


@dataclass(frozen=True)
class AuthRateLimitError(Exception):
    retry_after: int

    def __str__(self) -> str:
        return "試行回数が多すぎます。しばらく待ってから再度お試しください。"


def check_login_allowed(request: HttpRequest, username: object) -> None:
    _check_allowed("login", _login_identities(request, username))


def record_login_failure(request: HttpRequest, username: object) -> None:
    identities = _login_identities(request, username)
    _record_attempt(
        "login-ip",
        identities[0],
        settings.AUTH_LOGIN_IP_MAX_FAILURES,
        settings.AUTH_LOGIN_WINDOW_SECONDS,
        settings.AUTH_LOGIN_LOCK_BASE_SECONDS,
    )
    _record_attempt(
        "login-account",
        identities[1],
        settings.AUTH_LOGIN_ACCOUNT_MAX_FAILURES,
        settings.AUTH_LOGIN_WINDOW_SECONDS,
        settings.AUTH_LOGIN_LOCK_BASE_SECONDS,
    )


def clear_login_failures(request: HttpRequest, username: object) -> None:
    account_identity = _login_identities(request, username)[1]
    AuthThrottle.objects.filter(
        action="login-account", identity_hash=_digest(account_identity)
    ).delete()


def consume_registration_attempt(request: HttpRequest, action: str) -> None:
    identity = f"ip:{_remote_ip(request)}"
    _check_allowed(action, (identity,))
    limit = (
        settings.AUTH_ADMIN_SETUP_MAX_ATTEMPTS
        if action == "admin-setup"
        else settings.AUTH_SIGNUP_MAX_ATTEMPTS
    )
    _record_attempt(
        action,
        identity,
        limit,
        settings.AUTH_REGISTRATION_WINDOW_SECONDS,
        settings.AUTH_REGISTRATION_WINDOW_SECONDS,
    )


def _check_allowed(action: str, identities: tuple[str, ...]) -> None:
    now = timezone.now()
    action_names = (
        ("login-ip", "login-account") if action == "login" else (action,)
    )
    retry_after = 0
    for action_name, identity in zip(action_names, identities, strict=True):
        blocked_until = (
            AuthThrottle.objects.filter(
                action=action_name,
                identity_hash=_digest(identity),
                blocked_until__gt=now,
            )
            .values_list("blocked_until", flat=True)
            .first()
        )
        if blocked_until:
            retry_after = max(retry_after, int((blocked_until - now).total_seconds()) + 1)
    if retry_after:
        raise AuthRateLimitError(retry_after)


def _record_attempt(
    action: str,
    identity: str,
    limit: int,
    window_seconds: int,
    lock_base_seconds: int,
) -> None:
    if limit <= 0:
        return
    now = timezone.now()
    with transaction.atomic():
        record, _ = AuthThrottle.objects.select_for_update().get_or_create(
            action=action,
            identity_hash=_digest(identity),
            defaults={"window_started_at": now},
        )
        if (now - record.window_started_at).total_seconds() >= window_seconds:
            record.attempt_count = 0
            record.window_started_at = now
            record.blocked_until = None
        record.attempt_count += 1
        if record.attempt_count >= limit:
            exponent = min(record.attempt_count - limit, 6)
            lock_seconds = min(
                lock_base_seconds * (2**exponent), settings.AUTH_MAX_LOCK_SECONDS
            )
            record.blocked_until = now + timedelta(seconds=lock_seconds)
        record.save()


def _login_identities(request: HttpRequest, username: object) -> tuple[str, str]:
    ip_identity = f"ip:{_remote_ip(request)}"
    normalized_username = str(username or "").strip().casefold()
    return ip_identity, f"{ip_identity}|username:{normalized_username}"


def _remote_ip(request: HttpRequest) -> str:
    forwarded_for = ""
    if settings.AUTH_RATE_LIMIT_TRUST_X_FORWARDED_FOR:
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",", 1)[0].strip()
    return forwarded_for or request.META.get("REMOTE_ADDR", "unknown")


def _digest(identity: str) -> str:
    material = f"{settings.SECRET_KEY}|{identity}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()

