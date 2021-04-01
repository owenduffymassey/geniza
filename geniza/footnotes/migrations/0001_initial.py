# Generated by Django 3.1.7 on 2021-04-01 22:12

from django.db import migrations, models
import django.db.models.deletion
import multiselectfield.db.fields
import sortedm2m.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('corpus', '0009_document_ordering_collection_meta'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='Creator',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(max_length=255)),
                ('first_name_en', models.CharField(max_length=255, null=True)),
                ('first_name_he', models.CharField(max_length=255, null=True)),
                ('first_name_ar', models.CharField(max_length=255, null=True)),
                ('last_name', models.CharField(max_length=255)),
                ('last_name_en', models.CharField(max_length=255, null=True)),
                ('last_name_he', models.CharField(max_length=255, null=True)),
                ('last_name_ar', models.CharField(max_length=255, null=True)),
            ],
            options={
                'ordering': ['last_name'],
            },
        ),
        migrations.CreateModel(
            name='SourceType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='Source',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('title_en', models.CharField(max_length=255, null=True)),
                ('title_he', models.CharField(max_length=255, null=True)),
                ('title_ar', models.CharField(max_length=255, null=True)),
                ('year', models.PositiveIntegerField(blank=True, null=True)),
                ('edition', models.CharField(blank=True, max_length=255)),
                ('volume', models.CharField(blank=True, max_length=255)),
                ('page_range', models.CharField(blank=True, help_text='The range of pages being cited. Do not include "p", "pg", etc. and follow the format # or #-#', max_length=255)),
                ('authors', sortedm2m.fields.SortedManyToManyField(help_text=None, to='footnotes.Creator')),
                ('language', models.ForeignKey(help_text='In what language was the source published?', null=True, on_delete=django.db.models.deletion.SET_NULL, to='corpus.languagescript')),
                ('source_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='footnotes.sourcetype')),
            ],
        ),
        migrations.CreateModel(
            name='Footnote',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('page_range', models.CharField(blank=True, help_text='The range of pages being cited. Do not include "p", "pg", etc. and follow the format # or #-#', max_length=255)),
                ('document_relation_types', multiselectfield.db.fields.MultiSelectField(choices=[('E', 'Edition'), ('T', 'Translation'), ('D', 'Discussion')], help_text='How does the document relate to a source?', max_length=5)),
                ('notes', models.TextField(blank=True)),
                ('object_id', models.PositiveIntegerField()),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='footnotes.source')),
            ],
        ),
    ]
