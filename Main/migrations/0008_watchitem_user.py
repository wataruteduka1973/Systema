import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("Main", "0007_watchitem"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="watchitem",
            name="url",
            field=models.CharField(max_length=1000),
        ),
        migrations.AddField(
            model_name="watchitem",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="watch_items",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="watchitem",
            constraint=models.UniqueConstraint(
                fields=("user", "url"), name="unique_user_watch_url"
            ),
        ),
    ]
