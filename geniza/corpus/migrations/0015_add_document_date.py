# Generated by Django 3.1 on 2021-06-02 21:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("corpus", "0014_rename_multifragment"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="doc_date_calendar",
            field=models.CharField(
                blank=True,
                choices=[
                    ("h", "Hijrī"),
                    ("k", "Kharājī"),
                    ("s", "Seleucid"),
                    ("am", "Anno Mundi"),
                ],
                help_text="Calendar according to which the document gives a date: Hijrī (AH); Kharājī (rare - mostly for fiscal docs); Seleucid (sometimes listed as Minyan Shetarot); Anno Mundi (Hebrew calendar)",
                max_length=2,
                verbose_name="Calendar",
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="doc_date_original",
            field=models.CharField(
                blank=True,
                help_text="explicit date on the document, in original format",
                max_length=255,
                verbose_name="Date on document (original)",
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="doc_date_standard",
            field=models.CharField(
                blank=True,
                help_text="CE date (convert to Julian before 1582, Gregorian after 1582). Use YYYY, YYYY-MM, YYYY-MM-DD format when possible",
                max_length=255,
                verbose_name="Document date (standardized)",
            ),
        ),
    ]
