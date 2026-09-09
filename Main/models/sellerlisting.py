from decimal import Decimal

from django.conf import settings
from django.db import models


class SellerListing(models.Model):
    STATUS_CHOICES = (
        ("draft", "登録済み"),
        ("active", "出品中"),
        ("ended", "終了"),
        ("sold", "落札済み"),
        ("cancelled", "見送り"),
        ("relist", "再出品待ち"),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    inventory_item = models.ForeignKey(
        "Main.InventoryItem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="seller_listings",
    )
    external_listing_id = models.CharField(max_length=255, db_index=True)
    url = models.CharField(max_length=1000)
    name = models.TextField()
    condition = models.CharField(max_length=20, default="unknown", db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    observed_status = models.CharField(max_length=20, default="unknown")
    start_price = models.PositiveBigIntegerField(default=0)
    current_price = models.PositiveBigIntegerField(default=0)
    buyout_price = models.PositiveBigIntegerField(null=True, blank=True)
    bidding = models.PositiveIntegerField(default=0)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    market_median = models.PositiveBigIntegerField(default=0)
    predicted_sale_price = models.PositiveBigIntegerField(null=True, blank=True)
    acquisition_cost = models.PositiveBigIntegerField(default=0)
    purchase_shipping_cost = models.PositiveBigIntegerField(default=0)
    purchase_decision = models.JSONField(default=dict, blank=True)
    missing_cost_fields = models.JSONField(default=list, blank=True)
    shipping_cost_estimate = models.PositiveBigIntegerField(default=0)
    packaging_cost_estimate = models.PositiveBigIntegerField(default=0)
    other_cost_estimate = models.PositiveBigIntegerField(default=0)
    fee_rate = models.DecimalField(max_digits=6, decimal_places=5, default=Decimal("0.10"))
    target_profit = models.PositiveBigIntegerField(default=0)
    note = models.TextField(blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "-pk")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "external_listing_id"), name="seller_owner_external_unique"
            ),
            models.UniqueConstraint(fields=("user", "url"), name="seller_owner_url_unique"),
            models.CheckConstraint(
                condition=models.Q(fee_rate__gte=0, fee_rate__lte=1), name="seller_fee_rate_range"
            ),
        ]
        indexes = [
            models.Index(fields=("user", "status", "-updated_at"), name="seller_owner_status_idx"),
            models.Index(fields=("user", "ends_at"), name="seller_owner_end_idx"),
        ]


class SellerListingSnapshot(models.Model):
    seller_listing = models.ForeignKey(
        SellerListing, on_delete=models.CASCADE, related_name="snapshots"
    )
    current_price = models.PositiveBigIntegerField()
    bidding = models.PositiveIntegerField()
    remaining_seconds = models.PositiveBigIntegerField(null=True)
    market_median = models.PositiveBigIntegerField()
    predicted_sale_price = models.PositiveBigIntegerField()
    estimated_fee = models.PositiveBigIntegerField(null=True)
    estimated_profit = models.BigIntegerField(null=True)
    calculation_inputs = models.JSONField(default=dict)
    observed_status = models.CharField(max_length=20)
    observed_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ("-observed_at", "-pk")
        constraints = [
            models.UniqueConstraint(
                fields=("seller_listing", "observed_at"), name="seller_snapshot_observed_unique"
            )
        ]
        indexes = [
            models.Index(fields=("seller_listing", "-observed_at"), name="seller_snapshot_time_idx")
        ]


class SaleRecord(models.Model):
    seller_listing = models.OneToOneField(
        SellerListing, on_delete=models.CASCADE, related_name="sale_record"
    )
    sale_price = models.PositiveBigIntegerField()
    actual_fee = models.PositiveBigIntegerField(default=0)
    actual_shipping_cost = models.PositiveBigIntegerField(default=0)
    actual_packaging_cost = models.PositiveBigIntegerField(default=0)
    actual_other_cost = models.PositiveBigIntegerField(default=0)
    sold_at = models.DateTimeField()
    confirmed_profit = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-sold_at", "-pk")
