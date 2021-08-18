# Generated by Django 3.1 on 2021-08-17 21:07

from django.db import migrations
from django.db.models import Count


def merge_indiabook_sources(apps, schema_editor):
    # after import from the metadata spreadsheet,
    # many of the india book sources were created
    # separately instead of being merged as expected/intended
    Source = apps.get_model("footnotes", "Source")
    Footnote = apps.get_model("footnotes", "Footnote")

    # get a list of all india book titles that are duplicated
    indiabook_titles = (
        Source.objects.filter(title__contains="India Book")
        .values("title")
        .annotate(title_count=Count("title"))
        .filter(title_count__gt=1)
        .values_list("title", flat=True)
    )

    # for each title:
    for indiabook_vol in indiabook_titles:
        # find all the sources (they are all the same in other fields)
        sources = Source.objects.filter(title=indiabook_vol)
        # use the first one as the main record
        primary_source = sources.first()
        # reassociate all the footnotes
        Footnote.objects.filter(source__title=indiabook_vol).update(
            source=primary_source
        )
        # delete remaining source records
        sources.exclude(pk=primary_source.pk).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0001_initial"),
        ("footnotes", "0011_split_goitein_typedtexts"),
    ]

    operations = [
        migrations.RunPython(merge_indiabook_sources, migrations.RunPython.noop)
    ]
