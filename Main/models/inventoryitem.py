from django.conf import settings
from django.db import models


class InventoryItem(models.Model):
    STATUS_CHOICES = (
        ("planned", "購入予定"),
        ("acquired", "仕入済み"),
        ("preparing", "出品準備中"),
        ("listed", "出品中"),
        ("sold", "販売済み"),
        ("disposed", "処分済み"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inventory_items",
    )
    source_watch_item = models.OneToOneField(
        "Main.WatchItem",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="inventory_item",
    )
    name = models.TextField()
    condition = models.CharField(max_length=20, default="unknown", db_index=True)
    category = models.CharField(max_length=100, blank=True, db_index=True)
    acquisition_cost = models.PositiveBigIntegerField(default=0)
    acquired_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="planned",
        db_index=True,
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name

    class Meta:
        ordering = ("-updated_at", "pk")
        indexes = [
            models.Index(
                fields=("user", "status", "-updated_at"),
                name="inventory_owner_status_idx",
            )
        ]
        verbose_name = "在庫商品"
        verbose_name_plural = "在庫商品"
