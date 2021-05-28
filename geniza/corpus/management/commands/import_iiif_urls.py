import csv
import re
from collections import defaultdict

from django.core.management.base import BaseCommand
from parasolr.django.signals import IndexableSignalHandler

from geniza.corpus.models import Fragment


class Command(BaseCommand):
    """Given a CSV of fragments and IIIF URLs, add those IIIF urls to their respective fragments in the database"""

    def __init__(self, *args, **options):
        super().__init__(*args, **options)

        self.stats = defaultdict(int)

        # disconnect solr indexing signals
        IndexableSignalHandler.disconnect()

    def add_arguments(self, parser):
        parser.add_argument("csv", type=str)
        parser.add_argument("-o", "--overwrite", action="store_true")
        parser.add_argument("-d", "--dryrun", action="store_true")

    def handle(self, *args, **options):
        self.csv_path = options.get("csv")
        self.overwrite = options.get("overwrite")
        self.dryrun = options.get("dryrun")

        with open(self.csv_path) as f:
            csvreader = csv.DictReader(f)
            for row in csvreader:
                self.import_iiif_url(row)

        self.stdout.write(f"URLs added: {self.stats['added']}")
        self.stdout.write(f"URLs updated: {self.stats['updated']}")
        self.stdout.write(f"Fragments not found: {self.stats['not-found']}")
        self.stdout.write(f"Fragments skipped: {self.stats['skipped']}")

    def view_to_iiif_url(self, url):
        """Get IIIF Manifest URL for a fragment when possible"""

        # cambridge iiif manifest links use the same id as view links
        # NOTE: should exclude search link like this one:
        # https://cudl.lib.cam.ac.uk/search?fileID=&keyword=T-s%2013J33.12&page=1&x=0&y=
        if "cudl.lib.cam.ac.uk/view/" in url:
            iiif_link = url.replace("/view/", "/iiif/")
            # view links end with /1 or /2 but iiif link does not include it
            iiif_link = re.sub(r"/\d$", "", iiif_link)
            return iiif_link

        # TODO: get new figgy iiif urls for JTS images based on shelfmark
        # if no url, return empty string for blank instead of null
        return ""

    def import_iiif_url(self, row):
        assert "shelfmark" in row and "url" in row
        try:
            fragment = Fragment.objects.get(shelfmark=row["shelfmark"])
        except Fragment.DoesNotExist:
            self.stats["not-found"] += 1
            return

        if not fragment.iiif_url or self.overwrite:
            if fragment.iiif_url:
                self.stats["updated"] += 1
            else:
                self.stats["added"] += 1

            fragment.iiif_url = self.view_to_iiif_url(row["url"])

            if self.dryrun:
                self.stdout.write(
                    f"Set {fragment} url to {self.view_to_iiif_url(row['url'])}"
                )
            else:
                fragment.save()
            return

        self.stats["skipped"] += 1
