# Generated by Django 3.1.6 on 2021-04-29 15:25

import gfklookupwidget.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("footnotes", "0004_add_source_url_notes_footnote_content"),
    ]

    operations = [
        migrations.AlterField(
            model_name="footnote",
            name="object_id",
            field=gfklookupwidget.fields.GfkLookupField(),
        ),
    ]
