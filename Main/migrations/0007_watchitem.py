from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("Main", "0006_searchwordlog_alter_scraping_options_and_more")]

    operations = [
        migrations.CreateModel(
            name="WatchItem",
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
                ("url", models.CharField(max_length=1000, unique=True)),
                ("search_keyword", models.CharField(blank=True, max_length=255)),
                ("current_price", models.PositiveBigIntegerField(default=0)),
                ("added_price", models.PositiveBigIntegerField(default=0)),
                ("bidding", models.PositiveIntegerField(default=0)),
                ("remaining_time", models.CharField(blank=True, max_length=100)),
                ("condition", models.CharField(default="unknown", max_length=20)),
                (
                    "condition_label",
                    models.CharField(default="未分類", max_length=50),
                ),
                ("market_median", models.PositiveBigIntegerField(default=0)),
                (
                    "buy_status",
                    models.CharField(db_index=True, default="insufficient", max_length=30),
                ),
                (
                    "buy_label",
                    models.CharField(default="判定材料不足", max_length=50),
                ),
                ("buy_score", models.PositiveSmallIntegerField(default=0)),
                ("buy_reason", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("last_checked_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "ウォッチ商品",
                "verbose_name_plural": "ウォッチリスト",
                "ordering": ("-buy_score", "-updated_at"),
            },
        )
    ]
