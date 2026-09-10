from decimal import Decimal

from django.conf import settings
from django.db import models


class AlertRule(models.Model):
    """A user-owned threshold rule for one Systema resource."""

    BUYER_RULE_TYPES = (
        ("price_below", "価格が指定額以下"),
        ("median_discount", "相場との差が指定率以上"),
        ("ending_soon", "終了までの時間が指定分以下"),
        ("low_bids", "入札数が指定数以下"),
        ("buy_score", "買い時点数が指定値以上"),
        ("new_listing", "新着候補"),
        ("within_budget", "購入上限内"),
    )
    SELLER_RULE_TYPES = (
        ("bid_stalled", "入札停滞"),
        ("ending_without_bids", "入札なしで終了間近"),
        ("loss_risk", "赤字見込み"),
        ("target_profit", "目標利益到達"),
        ("market_decline", "相場下落"),
    )
    RULE_TYPES = BUYER_RULE_TYPES + SELLER_RULE_TYPES

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="alert_rules"
    )
    saved_search = models.ForeignKey(
        "Main.SavedSearch",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="alert_rules",
    )
    watch_item = models.ForeignKey(
        "Main.WatchItem",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="alert_rules",
    )
    seller_listing = models.ForeignKey(
        "Main.SellerListing",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="alert_rules",
    )
    rule_type = models.CharField(max_length=40, choices=RULE_TYPES, db_index=True)
    threshold_value = models.DecimalField(max_digits=18, decimal_places=4)
    is_enabled = models.BooleanField(default=True, db_index=True)
    cooldown_minutes = models.PositiveIntegerField(default=60)
    last_triggered_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "-pk")
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        saved_search__isnull=False,
                        watch_item__isnull=True,
                        seller_listing__isnull=True,
                    )
                    | models.Q(
                        saved_search__isnull=True,
                        watch_item__isnull=False,
                        seller_listing__isnull=True,
                    )
                    | models.Q(
                        saved_search__isnull=True,
                        watch_item__isnull=True,
                        seller_listing__isnull=False,
                    )
                ),
                name="alert_rule_exactly_one_target",
            ),
            models.CheckConstraint(
                condition=models.Q(cooldown_minutes__gte=1),
                name="alert_rule_positive_cooldown",
            ),
            models.CheckConstraint(
                condition=models.Q(threshold_value__gte=Decimal("0")),
                name="alert_rule_nonnegative_threshold",
            ),
        ]
