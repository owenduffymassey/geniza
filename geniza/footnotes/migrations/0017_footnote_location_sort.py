# Generated by Django 3.2.11 on 2022-04-28 20:34

from django.db import migrations

import geniza.common.fields


class Migration(migrations.Migration):

    dependencies = [
        ("footnotes", "0016_rename_typed_texts"),
    ]

    operations = [
        migrations.AddField(
            model_name="footnote",
            name="location_sort",
            field=geniza.common.fields.NaturalSortField(
                db_index=True,
                default="",
                editable=False,
                for_field="location",
                max_length=255,
            ),
            preserve_default=False,
        ),
        migrations.AlterModelOptions(
            name="footnote",
            options={"ordering": ["source", "location_sort"]},
        ),
    ]
