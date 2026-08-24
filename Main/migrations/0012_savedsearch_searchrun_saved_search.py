import django
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _price_range_constraint():
    price_range = models.Q(maximum_price__isnull=True) | models.Q(
        minimum_price__lte=models.F("maximum_price")
    )
    arguments = {"name": "saved_search_valid_price_range"}
    arguments["condition" if django.VERSION >= (5, 1) else "check"] = price_range
    return models.CheckConstraint(**arguments)


class Migration(migrations.Migration):
    dependencies = [
        ("Main", "0011_searchrun_observability"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SavedSearch",
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
                ("name", models.CharField(max_length=100)),
                ("keyword", models.CharField(db_index=True, max_length=255)),
                (
                    "search_type",
                    models.CharField(
                        choices=[
                            ("closed", "落札相場"),
                            ("current", "現在価格"),
                            ("target", "ターゲット分析"),
                            ("prediction", "相場予想"),
                        ],
                        max_length=20,
                    ),
                ),
                ("condition", models.CharField(blank=True, max_length=20)),
                ("minimum_price", models.PositiveBigIntegerField(default=0)),
                ("maximum_price", models.PositiveBigIntegerField(blank=True, null=True)),
                ("excluded_keywords", models.JSONField(default=list)),
                (
                    "ending_within_minutes",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                ("sort_order", models.CharField(default="default", max_length=30)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="saved_searches",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "保存検索",
                "verbose_name_plural": "保存検索",
                "ordering": ("name", "id"),
            },
        ),
        migrations.AddConstraint(
            model_name="savedsearch",
            constraint=models.UniqueConstraint(
                fields=("user", "name"), name="unique_user_saved_search_name"
            ),
        ),
        migrations.AddConstraint(
            model_name="savedsearch",
            constraint=_price_range_constraint(),
        ),
        migrations.AddField(
            model_name="searchrun",
            name="saved_search",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="runs",
                to="Main.savedsearch",
            ),
        ),
    ]
