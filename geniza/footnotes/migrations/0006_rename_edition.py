# Generated by Django 3.1.7 on 2021-04-01 20:45

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('footnotes', '0004_load_sourcetypes'),
    ]

    operations = [
        migrations.RenameField(
            model_name='source',
            old_name='edition_number',
            new_name='edition',
        ),
    ]
