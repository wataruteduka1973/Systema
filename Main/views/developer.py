from collections import deque
from pathlib import Path

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.shortcuts import render

from Main.models.errorlog import ErrorLog
from Main.models.scraping import scraping
from Main.models.searchrun import SearchRun
from Main.models.searchwordlog import searchwordlog
from Main.models.watchitem import WatchItem


def _tail_log(path: Path, limit: int = 80) -> list[str]:
    if not path.is_file():
        return []
    try:
        with path.open(encoding="utf-8", errors="replace") as stream:
            return list(deque(stream, maxlen=limit))
    except OSError:
        return ["ログファイルを読み込めませんでした。"]


@staff_member_required(login_url="login")
def developer_dashboard(request):
    user_model = get_user_model()
    log_dir = Path(settings.LOG_DIR)
    context = {
        "user_count": user_model.objects.count(),
        "active_user_count": user_model.objects.filter(is_active=True).count(),
        "staff_count": user_model.objects.filter(is_staff=True).count(),
        "market_data_count": scraping.objects.count(),
        "search_log_count": searchwordlog.objects.count(),
        "search_run_count": SearchRun.objects.count(),
        "watch_count": WatchItem.objects.count(),
        "legacy_watch_count": WatchItem.objects.filter(user__isnull=True).count(),
        "error_count": ErrorLog.objects.count(),
        "recent_users": user_model.objects.order_by("-date_joined")[:10],
        "recent_errors": ErrorLog.objects.order_by("-timestamp")[:15],
        "logs": {
            "server.log": _tail_log(log_dir / "server.log"),
            "error.log": _tail_log(log_dir / "error.log"),
            "search.log": _tail_log(log_dir / "search.log"),
        },
    }
    return render(request, "developer/dashboard.html", context)
