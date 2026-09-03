"""ログインユーザーと匿名セッションを同じ所有者として扱う補助処理。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.sessions.backends.db import SessionStore
from django.db import transaction
from django.db.models import Q


@dataclass(frozen=True)
class RequestOwner:
    user: Any | None
    session_key: str

    @property
    def model_values(self) -> dict[str, Any]:
        return {"user": self.user, "session_key": "" if self.user else self.session_key}


def get_request_owner(request: Any) -> RequestOwner:
    user = getattr(request, "user", None)
    if getattr(user, "is_authenticated", False):
        return RequestOwner(user=user, session_key="")
    if not hasattr(request, "session"):
        request.session = SessionStore()
    if not request.session.session_key:
        request.session.create()
    return RequestOwner(user=None, session_key=request.session.session_key or "")


def owner_query(owner: RequestOwner, prefix: str = "") -> Q:
    field = f"{prefix}__" if prefix else ""
    if owner.user is not None:
        return Q(**{f"{field}user": owner.user})
    return Q(**{f"{field}user__isnull": True, f"{field}session_key": owner.session_key})


def claim_session_data(user: Any, session_key: str) -> None:
    """ログイン前の匿名データをユーザーへ安全に引き継ぐ。"""
    if not session_key:
        return
    from Main.models.searchrun import SearchRun
    from Main.models.searchwordlog import searchwordlog
    from Main.models.watchitem import WatchItem, WatchPriceSnapshot

    with transaction.atomic():
        anonymous_items = list(WatchItem.objects.filter(user__isnull=True, session_key=session_key))
        for item in anonymous_items:
            existing = WatchItem.objects.filter(user=user, url=item.url).first()
            if existing:
                WatchPriceSnapshot.objects.filter(watch_item=item).update(watch_item=existing)
                if item.updated_at > existing.updated_at:
                    for field in (
                        "name",
                        "search_keyword",
                        "current_price",
                        "bidding",
                        "remaining_time",
                        "condition",
                        "condition_label",
                        "market_median",
                        "buy_status",
                        "buy_label",
                        "buy_score",
                        "buy_reason",
                    ):
                        setattr(existing, field, getattr(item, field))
                    existing.save()
                item.delete()
            else:
                item.user = user
                item.session_key = ""
                item.save(update_fields=("user", "session_key"))
        SearchRun.objects.filter(user__isnull=True, session_key=session_key).update(
            user=user, session_key=""
        )
        searchwordlog.objects.filter(user__isnull=True, session_key=session_key).update(
            user=user, session_key=""
        )
