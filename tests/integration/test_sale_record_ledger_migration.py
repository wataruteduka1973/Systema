"""Migrations 0024-0026 turn SaleRecord into an owner-held ledger without losing data."""

from datetime import datetime, timezone

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db(transaction=True)

BEFORE = [("Main", "0023_watch_item_primary_image")]
AFTER = [("Main", "0026_sale_record_owner_required")]


def _migrate(targets):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps


@pytest.fixture(autouse=True)
def _restore_latest_schema():
    """Leave the database at the newest migrations, so later tests see every column."""
    yield
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


def test_backfill_copies_owner_snapshot_and_splits_exact_purchase_cost():
    old = _migrate(BEFORE)
    user = old.get_model("auth", "User").objects.create(username="ledger-owner")
    listing = old.get_model("Main", "SellerListing").objects.create(
        user=user,
        external_listing_id="e123456789",
        url="https://auctions.yahoo.co.jp/jp/auction/e123456789",
        name="移行前の商品",
        acquisition_cost=9999,  # changed after the sale; must not leak into the split
        purchase_shipping_cost=300,
        status="sold",
    )
    # Confirmed with acquisition 3000 + purchase shipping 300: 10000 - 3300 - (1000+500+200+0).
    old.get_model("Main", "SaleRecord").objects.create(
        seller_listing=listing,
        sale_price=10000,
        actual_fee=1000,
        actual_shipping_cost=500,
        actual_packaging_cost=200,
        actual_other_cost=0,
        sold_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        confirmed_profit=5000,
        category="カメラ",
    )

    new = _migrate(AFTER)
    record = new.get_model("Main", "SaleRecord").objects.get()

    assert record.user_id == user.pk
    assert record.item_name == "移行前の商品"
    assert record.listing_url == "https://auctions.yahoo.co.jp/jp/auction/e123456789"
    assert (record.acquisition_cost, record.purchase_shipping_cost) == (3000, 300)
    costs = (
        record.acquisition_cost
        + record.purchase_shipping_cost
        + record.actual_fee
        + record.actual_shipping_cost
        + record.actual_packaging_cost
        + record.actual_other_cost
    )
    assert record.sale_price - costs == record.confirmed_profit

    # Deleting the listing now only unlinks the record.
    new.get_model("Main", "SellerListing").objects.all().delete()
    assert new.get_model("Main", "SaleRecord").objects.get().seller_listing_id is None
