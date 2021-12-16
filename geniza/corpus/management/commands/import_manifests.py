"""
Importing IIIF manifests to be cached in the database.

"""

from django.core.management.base import BaseCommand
from djiffy.importer import ManifestImporter
from djiffy.models import Manifest

from geniza.corpus.models import Fragment


class Command(BaseCommand):
    """Import IIIF manifests into the local database."""

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "path",
            nargs="*",
            help="One or more IIIF Collections or Manifests as file or URL (optional)",
        )
        parser.add_argument(
            "--update", action="store_true", help="Update previously imported manifests"
        )
        parser.add_argument(
            "--associate",
            action="store_true",
            help="Only associate fragments with imported manifests (no import)",
        )

    def handle(self, *args, **kwargs):
        # if fragment-manifest association is requested, run it and bail out
        if kwargs.get("associate"):
            self.associate_manifests()
            return

        # use command-line urls if specified
        iiif_urls = kwargs.get("path")
        # otherwise, import all iiif manifests referenced by fragments in the db
        if not iiif_urls:
            iiif_urls = set(
                Fragment.objects.exclude(iiif_url="").values_list("iiif_url", flat=True)
            )
            # if we're not updating, filter out the ones we already have
            if not kwargs["update"]:
                already_imported = set(Manifest.objects.values_list("uri", flat=True))
                self.stdout.write(
                    "Skipping %d previously imported IIIF manifests"
                    % len(already_imported)
                )
                iiif_urls = iiif_urls - already_imported

            self.stdout.write(
                "%d IIIF urls associated with fragments to import" % len(iiif_urls)
            )

        ManifestImporter(
            stdout=self.stdout,
            stderr=self.stderr,
            style=self.style,
            update=kwargs["update"],
        ).import_paths(iiif_urls)

        self.associate_manifests()

    def associate_manifests(self):
        # update fragments with iiif urls to add foreign keys to the new manifests
        fragments = Fragment.objects.exclude(iiif_url="").filter(manifest__isnull=True)
        for fragment in fragments:
            fragment.manifest = Manifest.objects.filter(uri=fragment.iiif_url).first()
            if fragment.manifest:
                fragment.save()
                # TODO log entry?
