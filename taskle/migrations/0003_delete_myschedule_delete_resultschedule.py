# Generated by Django 5.0.1 on 2024-02-01 06:36

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('taskle', '0002_scraping'),
    ]

    operations = [
        migrations.DeleteModel(
            name='MYschedule',
        ),
        migrations.DeleteModel(
            name='ResultSchedule',
        ),
    ]
