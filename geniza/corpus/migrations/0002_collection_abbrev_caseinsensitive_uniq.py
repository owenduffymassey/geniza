# Generated by Django 3.1.6 on 2021-02-23 22:09

from django.db import migrations, models
import psqlextra.indexes.case_insensitive_unique_index


class Migration(migrations.Migration):

    dependencies = [
        ('corpus', '0001_create_collection_languagescript'),
    ]

    operations = [
        migrations.AlterField(
            model_name='collection',
            name='abbrev',
            field=models.CharField(max_length=255, verbose_name='Abbreviation'),
        ),
        migrations.AddIndex(
            model_name='collection',
            index=psqlextra.indexes.case_insensitive_unique_index.CaseInsensitiveUniqueIndex(fields=['abbrev'], name='corpus_coll_abbrev_cec266_idx'),
        ),
    ]
