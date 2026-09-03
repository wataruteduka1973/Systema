import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("Main", "0015_watchlist_phase2"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryItem",
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
                ("name", models.TextField()),
                ("condition", models.CharField(db_index=True, default="unknown", max_length=20)),
                ("category", models.CharField(blank=True, db_index=True, max_length=100)),
                ("acquisition_cost", models.PositiveBigIntegerField(default=0)),
                ("acquired_at", models.DateTimeField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("planned", "購入予定"),
                            ("acquired", "仕入済み"),
                            ("preparing", "出品準備中"),
                            ("listed", "出品中"),
                            ("sold", "販売済み"),
                            ("disposed", "処分済み"),
                        ],
                        db_index=True,
                        default="planned",
                        max_length=20,
                    ),
                ),
                ("note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "source_watch_item",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="inventory_item",
                        to="Main.watchitem",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inventory_items",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "在庫商品",
                "verbose_name_plural": "在庫商品",
                "ordering": ("-updated_at", "pk"),
                "indexes": [
                    models.Index(
                        fields=["user", "status", "-updated_at"],
                        name="inventory_owner_status_idx",
                    )
                ],
            },
        )
    ]
