from django.conf import settings
from django.db import models


class CostSettings(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    assumptions = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)


class PurchaseDecision(models.Model):
    watch_item = models.ForeignKey(
        "Main.WatchItem", on_delete=models.CASCADE, related_name="purchase_decisions"
    )
    snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-pk",)
