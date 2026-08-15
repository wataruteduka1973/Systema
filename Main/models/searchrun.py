from django.conf import settings
from django.db import models


class SearchRun(models.Model):
    CLOSED = "closed"
    CURRENT = "current"
    TARGET = "target"
    PREDICTION = "prediction"
    SEARCH_TYPES = (
        (CLOSED, "落札相場"),
        (CURRENT, "現在価格"),
        (TARGET, "ターゲット分析"),
        (PREDICTION, "相場予想"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="search_runs",
    )
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    keyword = models.CharField(max_length=255, db_index=True)
    search_type = models.CharField(max_length=20, choices=SEARCH_TYPES, default=CLOSED)
    item_count = models.PositiveIntegerField(default=0)
    succeeded = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self) -> str:
        return f"{self.keyword} ({self.get_search_type_display()})"

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "検索実行"
        verbose_name_plural = "検索実行履歴"
