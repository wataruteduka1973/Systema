from django.db import models


class AuthThrottle(models.Model):
    """認証試行の匿名化された回数・遮断状態。"""

    action = models.CharField(max_length=30)
    identity_hash = models.CharField(max_length=64)
    attempt_count = models.PositiveIntegerField(default=0)
    window_started_at = models.DateTimeField()
    blocked_until = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("action", "identity_hash"),
                name="unique_auth_throttle_identity",
            )
        ]
        indexes = [models.Index(fields=("action", "blocked_until"))]

