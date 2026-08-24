import django
from django.conf import settings
from django.db import models


def _price_range_constraint():
    price_range = models.Q(maximum_price__isnull=True) | models.Q(
        minimum_price__lte=models.F("maximum_price")
    )
    arguments = {"name": "saved_search_valid_price_range"}
    arguments["condition" if django.VERSION >= (5, 1) else "check"] = price_range
    return models.CheckConstraint(**arguments)


class SavedSearch(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_searches",
    )
    name = models.CharField(max_length=100)
    keyword = models.CharField(max_length=255, db_index=True)
    condition = models.CharField(max_length=20, blank=True)
    minimum_price = models.PositiveBigIntegerField(default=0)
    maximum_price = models.PositiveBigIntegerField(blank=True, null=True)
    excluded_keywords = models.JSONField(default=list)
    ending_within_minutes = models.PositiveIntegerField(blank=True, null=True)
    sort_order = models.CharField(max_length=30, default="default")
    is_active = models.BooleanField(default=True, db_index=True)
    last_run_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name

    class Meta:
        ordering = ("name", "id")
        constraints = [
            models.UniqueConstraint(fields=("user", "name"), name="unique_user_saved_search_name"),
            _price_range_constraint(),
        ]
        verbose_name = "保存検索"
        verbose_name_plural = "保存検索"
