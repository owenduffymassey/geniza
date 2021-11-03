import glob
import os.path
from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import models
from git import Repo

from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote


class Command(BaseCommand):
    def handle(self, *args, **options):
        # get settings for remote git repository url and local path
        gitrepo_url = settings.TEI_TRANSCRIPTIONS_GITREPO
        gitrepo_path = settings.TEI_TRANSCRIPTIONS_LOCAL_PATH

        # make sure we have latest tei content from git repository
        self.sync_git(gitrepo_url, gitrepo_path)

        stats = defaultdict(int)

        # iterate through all tei files in the repository
        for xmlfile in glob.iglob(os.path.join(gitrepo_path, "*.xml")):
            stats["xml"] += 1
            # get the document id from the filename (####.xml)
            pgpid = os.path.splitext(os.path.basename(xmlfile))[0]
            # in ONE case there is a duplicate id with b suffix on the second
            try:
                pgpid = int(pgpid.strip("b"))
            except ValueError:
                self.stderr.write("Failed to generate integer PGPID from %s" % pgpid)
                continue

            # TODO: check empty files first, don't even look in db if no text

            # find the document in the database
            try:
                doc = Document.objects.get(
                    models.Q(id=pgpid) | models.Q(old_pgpids__contains=[pgpid])
                )
            except Document.DoesNotExist:
                stats["document_not_found"] += 1
                self.stdout.write("Document %s not found in database" % pgpid)
                continue

            editions = doc.footnotes.editions()
            if editions.count() > 1:
                # print(xmlfile)
                # print('more than one edition')
                # print(editions)
                # print(list(ed.source for ed in editions))
                stats["multiple_editions"] += 1
            elif not editions.exists():
                # print(xmlfile)
                # print('no edition')
                stats["no_edition"] += 1
            else:
                stats["one_edition"] += 1

            # start with the easy case? one edition footnote
            # start a list of questions! are multiple sources combined in the tei?

        # for each tei file, identify the document and update the transcription
        # iterate through all .xml files in git repo path; base name == pgpid
        # — how to identify corresponding footnote?
        # convert tei to iiif annotation with blocks & line numbers

        # report on what was done
        # include total number of transcription files,
        # documents with transcriptions, number of fragments, and how how many joins

        self.stdout.write(
            """Processed {xml:,} TEI/XML files.
{document_not_found:,} documents not found in database.
{multiple_editions:,} documents with multiple editions.
{no_edition:,} documents with no edition.
{one_edition:,} documents with one edition.
""".format(
                **stats
            )
        )

    def sync_git(self, gitrepo_url, local_path):
        # ensure git repository has been cloned and content is up to date

        # if directory does not yet exist, clone repository
        if not os.path.isdir(local_path):
            self.stdout.write(
                "Cloning TEI transcriptions repository to %s" % local_path
            )
            Repo.clone_from(url=gitrepo_url, to_path=local_path)
        else:
            # pull any changes since the last run
            Repo(local_path).remotes.origin.pull()


# port geniza tei code from prototype into a tei_geniza file
# generate html from tei that can be used to generate iiif annotations
# OR: just use the xslt in the repo? as good enough for now?

# check for empty transcription files
