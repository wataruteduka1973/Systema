"""Bounded, privacy-safe database aggregates for staff monitoring."""

from datetime import timedelta
from typing import Any

from django.apps import apps
from django.db.models import Avg, Case, CharField, Count, Max, Q, Value, When
from django.db.models.functions import TruncDate
from django.utils import timezone

from Main.models.errorlog import ErrorLog
from Main.models.scraping import scraping
from Main.models.searchrun import SearchRun
from Main.models.watchitem import WatchItem

FAILURES = {
    "external_service_unavailable": "Yahoo取得失敗",
    "html_parse_error": "HTML解析失敗",
    "unexpected_error": "内部処理失敗",
    "no_data": "検索結果なし",
    "insufficient_data": "分析データ不足",
    "other": "未分類",
}
ERROR_KINDS = {"http": "HTTP", "browser": "ブラウザー", "other": "その他"}
LEVELS = {"warning": "警告（HTTP 4xx）", "error": "エラー（その他）"}
TRIGGERS = {"manual": "手動", "saved": "保存検索", "alert": "アラート", "scheduled": "定期実行"}
ACTORS = {"user": "ログイン", "anonymous": "匿名セッション", "unowned": "所有者なし"}


def monitoring_snapshot(*, days: int, level: str, kind: str) -> dict[str, Any]:
    now = timezone.now()
    cutoff = now - timedelta(days=days)
    runs = SearchRun.objects.filter(created_at__gte=cutoff, created_at__lte=now)
    totals = runs.aggregate(
        total=Count("pk"),
        successful=Count("pk", filter=Q(succeeded=True)),
        timed=Count("duration_ms"),
        average_ms=Avg("duration_ms"),
        maximum_ms=Max("duration_ms"),
    )
    totals["success_rate"] = (
        round(100 * totals["successful"] / totals["total"], 1) if totals["total"] else None
    )
    actor = Case(
        When(user__isnull=False, then=Value("user")),
        When(~Q(session_key=""), then=Value("anonymous")),
        default=Value("unowned"),
        output_field=CharField(),
    )
    actor_counts = runs.annotate(actor=actor).values("actor").annotate(count=Count("pk"))
    trigger_counts = (
        runs.annotate(
            safe_trigger=Case(
                *[When(trigger=key, then=Value(key)) for key in TRIGGERS],
                default=Value("other"),
                output_field=CharField(),
            )
        )
        .values("safe_trigger")
        .annotate(count=Count("pk"))
    )
    failures = (
        runs.filter(succeeded=False)
        .annotate(
            safe_failure=Case(
                *[When(failure_code=key, then=Value(key)) for key in FAILURES if key != "other"],
                default=Value("other"),
                output_field=CharField(),
            )
        )
        .values("safe_failure")
        .annotate(count=Count("pk"))
    )
    errors = ErrorLog.objects.filter(timestamp__gte=cutoff, timestamp__lte=now).annotate(
        kind=Case(
            When(error_code="client_error", then=Value("browser")),
            When(error_code__in=[str(i) for i in range(400, 600)], then=Value("http")),
            default=Value("other"),
            output_field=CharField(),
        ),
        level=Case(
            When(error_code__in=[str(i) for i in range(400, 500)], then=Value("warning")),
            default=Value("error"),
            output_field=CharField(),
        ),
    )
    if level:
        errors = errors.filter(level=level)
    if kind:
        errors = errors.filter(kind=kind)
    daily = (
        errors.annotate(day=TruncDate("timestamp"))
        .values("day")
        .annotate(count=Count("pk"))
        .order_by("day")
    )
    recent = errors.order_by("-timestamp", "-pk").values("timestamp", "kind", "level")[:20]
    # Aggregate identities inside the DB; never return session keys or user IDs.
    recent_runs = SearchRun.objects.filter(
        created_at__gte=now - timedelta(hours=1), created_at__lte=now
    )
    high_users = (
        recent_runs.filter(user__isnull=False)
        .values("user_id")
        .annotate(count=Count("pk"))
        .filter(count__gte=60)
        .count()
    )
    high_sessions = (
        recent_runs.filter(user__isnull=True)
        .exclude(session_key="")
        .values("session_key")
        .annotate(count=Count("pk"))
        .filter(count__gte=60)
        .count()
    )
    inventory = [
        {"label": str(model._meta.verbose_name), "count": model.objects.count()}
        for model in apps.get_app_config("Main").get_models()
    ]
    return {
        "generated_at": now,
        "cutoff": cutoff,
        "totals": totals,
        "actors": [{"label": ACTORS[row["actor"]], "count": row["count"]} for row in actor_counts],
        "triggers": [
            {"label": TRIGGERS.get(row["safe_trigger"], "その他"), "count": row["count"]}
            for row in trigger_counts
        ],
        "failures": [
            {"label": FAILURES[row["safe_failure"]], "count": row["count"]} for row in failures
        ],
        "daily_errors": list(daily),
        "error_count": errors.count(),
        "recent_errors": [
            {
                "timestamp": row["timestamp"],
                "kind": ERROR_KINDS[row["kind"]],
                "level": LEVELS[row["level"]],
            }
            for row in recent
        ],
        "inventory": inventory,
        "unowned_runs": SearchRun.objects.filter(user__isnull=True, session_key="").count(),
        "unowned_watches": WatchItem.objects.filter(user__isnull=True, session_key="").count(),
        "unowned_items": scraping.objects.filter(
            Q(search_run__isnull=True)
            | Q(search_run__user__isnull=True, search_run__session_key="")
        ).count(),
        "high_users": high_users,
        "high_sessions": high_sessions,
    }
