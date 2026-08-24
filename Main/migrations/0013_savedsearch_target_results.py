from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("Main", "0012_savedsearch_searchrun_saved_search")]

    operations = [
        migrations.RemoveField(model_name="savedsearch", name="search_type"),
        migrations.AddField(
            model_name="searchrun",
            name="result_snapshot",
            field=models.JSONField(default=dict),
        ),
    ]
