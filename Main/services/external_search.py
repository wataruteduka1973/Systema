"""外部検索APIに共通する入力検証と実行回数制限。"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest

from Main.services.exceptions import SearchInputError, SearchRateLimitError

CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


def normalize_search_keyword(value: object) -> str:
    """検索語を正規化し、外部サービスへ送信可能か検証する。"""
    keyword = unicodedata.normalize("NFKC", str(value or "")).strip()
    keyword = re.sub(r"[ \t\u3000]+", " ", keyword)
    if not keyword:
        raise SearchInputError("Keyword is required")
    if CONTROL_CHARACTERS.search(keyword):
        raise SearchInputError("検索キーワードに制御文字は使用できません")
    if len(keyword) > settings.EXTERNAL_SEARCH_KEYWORD_MAX_LENGTH:
        raise SearchInputError(
            f"検索キーワードは{settings.EXTERNAL_SEARCH_KEYWORD_MAX_LENGTH}文字以内で入力してください"
        )
    return keyword


def enforce_search_rate_limit(request: HttpRequest) -> None:
    """利用者単位の固定時間枠で外部検索の過剰実行を抑止する。"""
    limit = settings.EXTERNAL_SEARCH_RATE_LIMIT
    window = settings.EXTERNAL_SEARCH_RATE_WINDOW_SECONDS
    if limit <= 0:
        return

    identity = _request_identity(request)
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    key = f"external-search-rate:{digest}"
    if cache.add(key, 1, timeout=window):
        return
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window)
        return
    if count > limit:
        raise SearchRateLimitError(window)


def _request_identity(request: HttpRequest) -> str:
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return f"user:{user.pk}"
    session = getattr(request, "session", None)
    session_key = getattr(session, "session_key", None)
    if session_key:
        return f"session:{session_key}"
    forwarded_for = ""
    if settings.EXTERNAL_SEARCH_TRUST_X_FORWARDED_FOR:
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",", 1)[0].strip()
    remote_addr = forwarded_for or request.META.get("REMOTE_ADDR", "unknown")
    return f"ip:{remote_addr}"
