# Generated by Django 3.1 on 2021-05-14 15:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("footnotes", "0006_footnote_ordering"),
    ]

    operations = [
        migrations.AlterField(
            model_name="source",
            name="url",
            field=models.URLField(blank=True, max_length=300),
        ),
    ]
