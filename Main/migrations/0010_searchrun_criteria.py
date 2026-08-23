from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("Main", "0009_search_ownership")]

    operations = [
        migrations.AddField(
            model_name="searchrun",
            name="criteria_snapshot",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="searchrun",
            name="trigger",
            field=models.CharField(db_index=True, default="manual", max_length=20),
        ),
    ]
