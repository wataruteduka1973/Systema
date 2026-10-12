"""Make SaleRecord an independent sales ledger (step 1 of 3): add owner and listing snapshot
columns (nullable owner for now) and unlink instead of deleting when a listing is removed."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("Main", "0023_watch_item_primary_image"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="salerecord",
            name="user",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sale_records",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="salerecord", name="item_name", field=models.TextField(blank=True)
        ),
        migrations.AddField(
            model_name="salerecord",
            name="listing_url",
            field=models.CharField(blank=True, max_length=1000),
        ),
        migrations.AddField(
            model_name="salerecord",
            name="acquisition_cost",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="salerecord",
            name="purchase_shipping_cost",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="salerecord",
            name="seller_listing",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sale_record",
                to="Main.sellerlisting",
            ),
        ),
    ]
