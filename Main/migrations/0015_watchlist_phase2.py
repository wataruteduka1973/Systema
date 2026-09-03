import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("Main", "0014_auththrottle")]

    operations = [
        migrations.AddField(
            model_name="watchitem",
            name="note",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="watchitem",
            name="priority",
            field=models.PositiveSmallIntegerField(db_index=True, default=0),
        ),
        migrations.AddField(
            model_name="watchitem",
            name="category",
            field=models.CharField(blank=True, db_index=True, max_length=100),
        ),
        migrations.AddField(
            model_name="watchitem",
            name="lifecycle_status",
            field=models.CharField(
                choices=[
                    ("active", "追跡中"),
                    ("purchased", "購入済み"),
                    ("skipped", "見送り"),
                    ("ended", "終了"),
                    ("archived", "アーカイブ"),
                ],
                db_index=True,
                default="active",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="watchitem",
            name="ended_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="watchitem",
            name="archived_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="watchitem",
            name="last_price_change_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="WatchPriceSnapshot",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("price", models.PositiveBigIntegerField()),
                ("bidding", models.PositiveIntegerField(default=0)),
                ("remaining_seconds", models.PositiveIntegerField(blank=True, null=True)),
                ("condition", models.CharField(default="unknown", max_length=20)),
                ("observed_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "watch_item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="price_snapshots",
                        to="Main.watchitem",
                    ),
                ),
            ],
            options={
                "ordering": ("observed_at", "pk"),
                "indexes": [
                    models.Index(
                        fields=["watch_item", "-observed_at"],
                        name="watch_snapshot_recent_idx",
                    )
                ],
            },
        ),
    ]
