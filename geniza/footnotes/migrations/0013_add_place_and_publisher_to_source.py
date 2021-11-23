# Generated by Django 3.2.8 on 2021-11-23 14:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("footnotes", "0012_merge_indiabook_sources"),
    ]

    operations = [
        migrations.AddField(
            model_name="source",
            name="place_published",
            field=models.CharField(
                blank=True,
                help_text="Place where the work was published",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="source",
            name="publisher",
            field=models.CharField(
                blank=True, help_text="Publisher name", max_length=255
            ),
        ),
    ]
