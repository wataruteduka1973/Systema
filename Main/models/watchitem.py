from django.db import models


class WatchItem(models.Model):
    """Systema内で追跡する出品中の商品。"""

    name = models.TextField()
    url = models.CharField(max_length=1000, unique=True)
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_checked_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name

    class Meta:
        ordering = ("-buy_score", "-updated_at")
        verbose_name = "ウォッチ商品"
        verbose_name_plural = "ウォッチリスト"
