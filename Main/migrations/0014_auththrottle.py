from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("Main", "0013_savedsearch_target_results")]

    operations = [
        migrations.CreateModel(
            name="AuthThrottle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=30)),
                ("identity_hash", models.CharField(max_length=64)),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("window_started_at", models.DateTimeField()),
                ("blocked_until", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "indexes": [models.Index(fields=["action", "blocked_until"], name="Main_authth_action_ed58ff_idx")],
                "constraints": [models.UniqueConstraint(fields=("action", "identity_hash"), name="unique_auth_throttle_identity")],
            },
        )
    ]
