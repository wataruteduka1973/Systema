"""Step 2 of 3: copy owner, name, URL and purchase costs from each record's listing.

The purchase side of a record is exact: sale price - confirmed profit - selling costs, because the
profit was computed from those values at confirmation. The listing's current purchase costs may
have changed since, so they are only used to split that exact total: purchase shipping is capped
at the total and the rest is acquisition cost.
"""

from django.db import migrations


def backfill(apps, schema_editor):
    SaleRecord = apps.get_model("Main", "SaleRecord")
    for record in SaleRecord.objects.select_related("seller_listing").iterator():
        listing = record.seller_listing
        selling = (
            record.actual_fee
            + record.actual_shipping_cost
            + record.actual_packaging_cost
            + record.actual_other_cost
        )
        purchase = max(record.sale_price - record.confirmed_profit - selling, 0)
        shipping = min(listing.purchase_shipping_cost, purchase)
        record.user_id = listing.user_id
        record.item_name = listing.name
        record.listing_url = listing.url
        record.purchase_shipping_cost = shipping
        record.acquisition_cost = purchase - shipping
        record.save(
            update_fields=(
                "user",
                "item_name",
                "listing_url",
                "purchase_shipping_cost",
                "acquisition_cost",
            )
        )


class Migration(migrations.Migration):
    dependencies = [("Main", "0024_sale_record_ledger_fields")]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
