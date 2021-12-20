# Generated by Django 3.2.6 on 2021-12-13 22:43

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("djiffy", "0003_extra_data_revisions"),
        ("corpus", "0023_alter_document_tags"),
    ]

    operations = [
        migrations.AddField(
            model_name="fragment",
            name="manifest",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="djiffy.manifest",
            ),
        ),
    ]
