from django.conf import settings
from django.db import models


class Notification(models.Model):
    """A user-owned in-app notification created from a completed system event."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    event_type = models.CharField(max_length=40, db_index=True)
    title = models.CharField(max_length=200)
    message = models.TextField()
    target_url = models.CharField(max_length=1000, blank=True)
    source_type = models.CharField(max_length=40)
    source_id = models.BigIntegerField(blank=True, null=True)
    dedupe_key = models.CharField(max_length=255)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(blank=True, null=True, db_index=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "dedupe_key"),
                name="unique_user_notification_dedupe",
            )
        ]
