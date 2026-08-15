import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("Main", "0008_watchitem_user"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SearchRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_key", models.CharField(blank=True, db_index=True, max_length=40)),
                ("keyword", models.CharField(db_index=True, max_length=255)),
                ("search_type", models.CharField(choices=[("closed", "落札相場"), ("current", "現在価格"), ("target", "ターゲット分析"), ("prediction", "相場予想")], default="closed", max_length=20)),
                ("item_count", models.PositiveIntegerField(default=0)),
                ("succeeded", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="search_runs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "検索実行", "verbose_name_plural": "検索実行履歴", "ordering": ("-created_at",)},
        ),
        migrations.AddField(model_name="scraping", name="search_run", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="items", to="Main.searchrun")),
        migrations.AddField(model_name="searchwordlog", name="session_key", field=models.CharField(blank=True, db_index=True, max_length=40)),
        migrations.AddField(model_name="searchwordlog", name="user", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="search_word_logs", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="watchitem", name="session_key", field=models.CharField(blank=True, db_index=True, max_length=40)),
        migrations.RemoveConstraint(model_name="watchitem", name="unique_user_watch_url"),
        migrations.AddConstraint(model_name="watchitem", constraint=models.UniqueConstraint(condition=models.Q(user__isnull=False), fields=("user", "url"), name="unique_user_watch_url")),
        migrations.AddConstraint(model_name="watchitem", constraint=models.UniqueConstraint(condition=models.Q(user__isnull=True) & ~models.Q(session_key=""), fields=("session_key", "url"), name="unique_session_watch_url")),
    ]
