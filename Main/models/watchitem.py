from django.conf import settings
from django.db import models


class WatchItem(models.Model):
    """Systema内で追跡する出品中の商品。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="watch_items",
    )
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    name = models.TextField()
    url = models.CharField(max_length=1000)
    search_keyword = models.CharField(max_length=255, blank=True)
    current_price = models.PositiveBigIntegerField(default=0)
    added_price = models.PositiveBigIntegerField(default=0)
    bidding = models.PositiveIntegerField(default=0)
    remaining_time = models.CharField(max_length=100, blank=True)
    condition = models.CharField(max_length=20, default="unknown")
    condition_label = models.CharField(max_length=50, default="未分類")
    market_median = models.PositiveBigIntegerField(default=0)
    buy_status = models.CharField(max_length=30, default="insufficient", db_index=True)
    buy_label = models.CharField(max_length=50, default="判定材料不足")
    buy_score = models.PositiveSmallIntegerField(default=0)
    buy_reason = models.TextField(blank=True)
    note = models.TextField(blank=True)
    priority = models.PositiveSmallIntegerField(default=0, db_index=True)
    category = models.CharField(max_length=100, blank=True, db_index=True)
    lifecycle_status = models.CharField(
        max_length=20,
        choices=(
            ("active", "追跡中"),
            ("purchased", "購入済み"),
            ("skipped", "見送り"),
            ("ended", "終了"),
            ("archived", "アーカイブ"),
        ),
        default="active",
        db_index=True,
    )
    ended_at = models.DateTimeField(blank=True, null=True)
    archived_at = models.DateTimeField(blank=True, null=True)
    last_price_change_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_checked_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name

    class Meta:
        ordering = ("-buy_score", "-updated_at")
        verbose_name = "ウォッチ商品"
        verbose_name_plural = "ウォッチリスト"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "url"),
                condition=models.Q(user__isnull=False),
                name="unique_user_watch_url",
            ),
            models.UniqueConstraint(
                fields=("session_key", "url"),
                condition=models.Q(user__isnull=True) & ~models.Q(session_key=""),
                name="unique_session_watch_url",
            ),
        ]


class WatchPriceSnapshot(models.Model):
    """ウォッチ商品の観測時点値。分析値はこの履歴から算出する。"""

    watch_item = models.ForeignKey(
        WatchItem,
        on_delete=models.CASCADE,
        related_name="price_snapshots",
    )
    price = models.PositiveBigIntegerField()
    bidding = models.PositiveIntegerField(default=0)
    remaining_seconds = models.PositiveIntegerField(blank=True, null=True)
    condition = models.CharField(max_length=20, default="unknown")
    observed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("observed_at", "pk")
        indexes = [
            models.Index(
                fields=("watch_item", "-observed_at"),
                name="watch_snapshot_recent_idx",
            )
        ]
