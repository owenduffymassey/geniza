# Generated by Django 3.1.6 on 2021-03-08 21:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('corpus', '0002_create_document_fragment'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='collection',
            name='unique_library_collection',
        ),
        migrations.RenameField(
            model_name='collection',
            old_name='collection',
            new_name='name',
        ),
        migrations.AddField(
            model_name='collection',
            name='lib_abbrev',
            field=models.CharField(blank=True, max_length=255, verbose_name='Library Abbreviation'),
        ),
        migrations.AlterField(
            model_name='collection',
            name='abbrev',
            field=models.CharField(blank=True, max_length=255, verbose_name='Collection Abbreviation'),
        ),
        migrations.AddConstraint(
            model_name='collection',
            constraint=models.CheckConstraint(check=models.Q(('library__regex', '.+'), ('name__regex', '.+'), _connector='OR'), name='req_library_or_name'),
        ),
        migrations.AddConstraint(
            model_name='collection',
            constraint=models.UniqueConstraint(fields=('library', 'name'), name='unique_library_name'),
        ),
    ]
