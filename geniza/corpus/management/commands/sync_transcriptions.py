import glob
import os.path
from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import models
from eulxml import xmlmap
from git import Repo

from geniza.corpus.models import Document
from geniza.corpus.tei_transcriptions import GenizaTei
from geniza.footnotes.models import Footnote


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "-n",
            "--noact",
            action="store_true",
            help="Do not save changes to the database",
        )

    def handle(self, *args, **options):
        # get settings for remote git repository url and local path
        gitrepo_url = settings.TEI_TRANSCRIPTIONS_GITREPO
        gitrepo_path = settings.TEI_TRANSCRIPTIONS_LOCAL_PATH

        # make sure we have latest tei content from git repository
        # self.sync_git(gitrepo_url, gitrepo_path)

        stats = defaultdict(int)
        # keep track of document ids with multiple digitized editions (likely merged records/joins)
        multiedition_docs = set()

        # iterate through all tei files in the repository
        for xmlfile in glob.iglob(os.path.join(gitrepo_path, "*.xml")):
            stats["xml"] += 1

            tei = xmlmap.load_xmlobject_from_file(xmlfile, GenizaTei)
            # some files are stubs with no content
            # check if there is no text content; report and skip
            if tei.no_content():
                self.stdout.write("%s has no text content, skipping" % xmlfile)
                stats["empty_tei"] += 1
                continue

            # get the document id from the filename (####.xml)
            pgpid = os.path.splitext(os.path.basename(xmlfile))[0]
            # in ONE case there is a duplicate id with b suffix on the second
            try:
                pgpid = int(pgpid.strip("b"))
            except ValueError:
                self.stderr.write("Failed to generate integer PGPID from %s" % pgpid)
                continue

            # find the document in the database
            try:
                doc = Document.objects.get(
                    models.Q(id=pgpid) | models.Q(old_pgpids__contains=[pgpid])
                )
            except Document.DoesNotExist:
                stats["document_not_found"] += 1
                self.stdout.write("Document %s not found in database" % pgpid)
                continue

            if doc.fragments.count() > 1:
                stats["joins"] += 1

            footnote = None

            editions = doc.footnotes.editions()
            if editions.count() > 1:
                # debugging output for footnote selection
                # print('more than one edition for %s' % xmlfile)
                # print(list(ed.source for ed in editions))
                # try filtering by current text content
                editions_with_content = editions.filter(content__isnull=False)
                # print('editions with content')
                # print(list(ed.source for ed in editions_with_content))
                stats["multiple_editions"] += 1
                if editions_with_content.count() > 1:
                    stats["multiple_editions_with_content"] += 1
                    multiedition_docs.add(doc.id)
                elif editions_with_content.count() == 1:
                    # if there was only one, assume it's the one to update
                    footnote = editions_with_content.first()
            elif not editions.exists():
                # debugging output for footnote selection
                # print('no edition for %s' % xmlfile)
                stats["no_edition"] += 1
            else:
                stats["one_edition"] += 1
                # if only one edition, update the transciption content there
                footnote = editions.first()

            # if we identified the correct footnote, update it
            if footnote:
                html = tei.text_to_html()
                text = tei.text_to_plaintext()
                if html:
                    footnote.content = {"html": html, "text": text}
                    if footnote.has_changed("content"):
                        # don't actually save in --noact mode
                        if not options["noact"]:
                            footnote.save()
                        # but still count as a change
                        stats["footnote_updated"] += 1
                else:
                    self.stderr.write("No html generated for %s" % doc.id)

            # NOTE: in *one* case there is a TEI file with translation content and
            # no transcription; will get reported as empty, but that's ok — it's out of scope
            # for this script and should be handled elsewhere.

        # report on what was done
        # include total number of transcription files,
        # documents with transcriptions, number of fragments, and how how many joins
        stats["multi_edition_docs"] = len(multiedition_docs)
        self.stdout.write(
            """Processed {xml:,} TEI/XML files; skipped {empty_tei:,} TEI files with no text content.
{document_not_found:,} documents not found in database.
{joins:,} documents with multiple fragments.
{multiple_editions:,} documents with multiple editions; {multiple_editions_with_content} multiple editions with content ({multi_edition_docs} unique documents).
{no_edition:,} documents with no edition.
{one_edition:,} documents with one edition.
Updated {footnote_updated:,} footnotes.
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
