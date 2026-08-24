from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("Main", "0010_searchrun_criteria")]

    operations = [
        migrations.AddField(
            model_name="searchrun",
            name="duration_ms",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="searchrun",
            name="failure_code",
            field=models.CharField(blank=True, db_index=True, max_length=40),
        ),
    ]
