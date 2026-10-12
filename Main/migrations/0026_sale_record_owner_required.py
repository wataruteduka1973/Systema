"""Step 3 of 3: every sale record has an owner; add the owner/time index used by analytics."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("Main", "0025_backfill_sale_record_ledger"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="salerecord",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sale_records",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name="salerecord",
            index=models.Index(fields=["user", "-sold_at"], name="sale_record_owner_time_idx"),
        ),
    ]
