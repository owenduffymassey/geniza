"""
Script to synchronize transcription content from PGP v3 TEI files
to an _interim_ html format in the database.

The script checks out and updates the transcription files from the
git repository, and then loops through all xml files and
identifies the document and footnote to update, if possible.

"""

import glob
import os.path
from collections import defaultdict

from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import models
from eulxml import xmlmap
from git import Repo

from geniza.corpus.models import Document
from geniza.corpus.tei_transcriptions import GenizaTei
from geniza.footnotes.models import Footnote, Source


class Command(BaseCommand):
    """Synchronize TEI transcriptions to edition footnote content"""

    v_normal = 1  # default verbosity

    def add_arguments(self, parser):
        parser.add_argument(
            "-n",
            "--noact",
            action="store_true",
            help="Do not save changes to the database",
        )

    # dict of footnotes that have been updated with list of TEI files, to track/prevent
    # TEI files resolving incorrectly to the same edition
    footnotes_updated = defaultdict(list)

    def handle(self, *args, **options):
        # get settings for remote git repository url and local path
        gitrepo_url = settings.TEI_TRANSCRIPTIONS_GITREPO
        gitrepo_path = settings.TEI_TRANSCRIPTIONS_LOCAL_PATH

        self.verbosity = options["verbosity"]
        self.noact_mode = options["noact"]

        # make sure we have latest tei content from git repository
        self.sync_git(gitrepo_url, gitrepo_path)

        if not self.noact_mode:
            # get content type and user for log entries, unless in no-act mode
            self.footnote_contenttype = ContentType.objects.get_for_model(Footnote)
            self.script_user = User.objects.get(username=settings.SCRIPT_USERNAME)

        self.stats = defaultdict(int)
        # after creating missing goitein unpublished edition notes, these will not be created again
        self.stats["footnote_created"] = 0
        # duplicates might not always happen
        self.stats["duplicate_footnote"] = 0
        # updates should not happen after initial sync when there are no TEI changes
        self.stats["footnote_updated"] = 0
        # keep track of document ids with multiple digitized editions (likely merged records/joins)
        self.multiedition_docs = set()

        # iterate through all tei files in the repository
        for xmlfile in glob.iglob(os.path.join(gitrepo_path, "*.xml")):
            self.stats["xml"] += 1
            xmlfile_basename = os.path.basename(xmlfile)

            tei = xmlmap.load_xmlobject_from_file(xmlfile, GenizaTei)
            # some files are stubs with no content
            # check if there is no text content; report and skip
            if tei.no_content():
                if self.verbosity >= self.v_normal:
                    self.stdout.write("%s has no text content, skipping" % xmlfile)
                self.stats["empty_tei"] += 1
                continue
            elif not tei.text.lines:
                self.stdout.write("%s has no lines (translation?), skipping" % xmlfile)
                self.stats["empty_tei"] += 1
                continue

            # get the document id from the filename (####.xml)
            pgpid = os.path.splitext(xmlfile_basename)[0]
            # in ONE case there is a duplicate id with b suffix on the second
            try:
                pgpid = int(pgpid.strip("b"))
            except ValueError:
                if self.verbosity >= self.v_normal:
                    self.stderr.write(
                        "Failed to generate integer PGPID from %s" % pgpid
                    )
                continue
            # can we rely on pgpid from xml?
            # but in some cases, it looks like a join 12047 + 12351

            # find the document in the database
            try:
                doc = Document.objects.get(
                    models.Q(id=pgpid) | models.Q(old_pgpids__contains=[pgpid])
                )
            except Document.DoesNotExist:
                self.stats["document_not_found"] += 1
                if self.verbosity >= self.v_normal:
                    self.stdout.write("Document %s not found in database" % pgpid)
                continue

            if doc.fragments.count() > 1:
                self.stats["joins"] += 1

            footnote = self.get_edition_footnote(doc, tei, xmlfile)
            # if we identified an appropriate footnote, update it
            if footnote:
                # if this footnote has already been chosen in the current script run, don't update again
                if self.footnotes_updated[footnote.pk]:
                    self.stderr.write(
                        "Footnote %s (PGPID %s) already updated with %s; not overwriting with %s"
                        % (
                            footnote.pk,
                            doc.pk,
                            ";".join(self.footnotes_updated[footnote.pk]),
                            xmlfile,
                        )
                    )
                    self.stats["duplicate_footnote"] += 1
                else:
                    self.footnotes_updated[footnote.pk].append(xmlfile)

                    html = tei.text_to_html()
                    text = tei.text_to_plaintext()
                    if html:
                        footnote.content = {"html": html, "text": text}
                        if footnote.has_changed("content"):

                            # don't actually save in --noact mode
                            if not self.noact_mode:
                                footnote.save()
                                # create a log entry to document the change
                                self.log_footnote_update(
                                    footnote, os.path.basename(xmlfile)
                                )

                            # count as a change whether in no-act mode or not
                            self.stats["footnote_updated"] += 1
                    else:
                        if self.verbosity >= self.v_normal:
                            self.stderr.write("No html generated for %s" % doc.id)

            # NOTE: in *one* case there is a TEI file with translation content and
            # no transcription; will get reported as empty, but that's ok — it's out of scope
            # for this script and should be handled elsewhere.

        # report on what was done
        # include total number of transcription files,
        # documents with transcriptions, number of fragments, and how how many joins
        self.stats["multi_edition_docs"] = len(self.multiedition_docs)
        self.stdout.write(
            """Processed {xml:,} TEI/XML files; skipped {empty_tei:,} TEI files with no transcription content.
{document_not_found:,} documents not found in database.
{joins:,} documents with multiple fragments.
{multiple_editions:,} documents with multiple editions; {multiple_editions_with_content} multiple editions with content ({multi_edition_docs} unique documents).
{no_edition:,} documents with no edition.
{one_edition:,} documents with one edition.
Updated {footnote_updated:,} footnotes (created {footnote_created:,}; skipped overwriting {duplicate_footnote}).
""".format(
                **self.stats
            )
        )

        for footnote_id, xmlfiles in self.footnotes_updated.items():
            if len(xmlfiles) > 1:
                self.stderr.write(
                    "Footnote pk %s updated more than once: %s"
                    % (footnote_id, ";".join(xmlfiles))
                )

    def get_edition_footnote(self, doc, tei, filename):
        """identify the edition footnote to be updated"""
        # NOTE: still needs to handle multiple editions, no editions
        editions = doc.footnotes.editions()

        if editions.count() > 1:
            self.stats["multiple_editions"] += 1

            # when there are multiple, try to identify correct edition by author names
            footnote = self.choose_edition_by_authors(tei, editions, doc)
            # if we got a match, use it
            if footnote:
                return footnote

            # if not, limit to editions with content and try again
            editions_with_content = editions.filter(content__isnull=False)
            footnote = self.choose_edition_by_authors(tei, editions_with_content, doc)
            if footnote:
                return footnote

            # if not, fallback to first edition
            if editions_with_content.count() == 1:
                self.stats["multiple_editions_with_content"] += 1
                self.multiedition_docs.add(doc.id)

                # if there was only one, assume it's the one to update
                # NOTE: this is potentially wrong!
                return editions_with_content.first()

        if not editions.exists():
            # no editions found; check if we can create a goitein unpublished edition footnote
            footnote = self.is_it_goitein(tei, doc)
            if footnote:
                return footnote

            self.stats["no_edition"] += 1
            if self.verbosity > self.v_normal:
                self.stdout.write("No edition found for %s" % filename)
                for line in tei.source:
                    self.stdout.write("\t%s" % line)
        else:
            self.stats["one_edition"] += 1
            # if only one edition, update the transciption content there
            return editions.first()

    def choose_edition_by_authors(self, tei, editions, doc):
        """Try to choose correct edition from a list based on author names;
        based on structured author names in the TEI"""
        if tei.source_authors:
            tei_authors = set(tei.source_authors)
            author_matches = []
            for ed in editions:
                ed_authors = set([auth.last_name for auth in ed.source.authors.all()])
                if ed_authors == tei_authors:
                    author_matches.append(ed)

            # if we got exactly one match, use that edition
            if len(author_matches) == 1:
                return author_matches[0]

            # if there were *no* author matches, see if we can create a goitein unpublished edition note
            if not author_matches:
                return self.is_it_goitein(tei, doc)

    def is_it_goitein(self, tei, doc):
        """Check if a TEI document is a Goitein edition. If no edition exists
        and we can identify based on the TEI as a Goitein unpublished edition,
        then create a new footnote."""
        source_info = str(tei.source[0]).lower()
        if "goitein" in source_info and (
            "unpublished editions" in source_info or "typed texts" in source_info
        ):
            if not self.noact_mode:
                footnote = self.create_goitein_footnote(doc)
                if footnote:
                    self.stats["footnote_created"] += 1
                    return footnote

    def create_goitein_footnote(self, doc):
        """Create a new footnote for a Goitein unpublished edition"""
        source = Source.objects.filter(
            authors__last_name="Goitein",
            title_en="unpublished editions",
            source_type__type="Unpublished",
            volume__startswith=Source.get_volume_from_shelfmark(doc.shelfmark),
        ).first()
        if not source:
            self.stderr.write(
                "Error finding Goitein unpublished editions source for %s"
                % doc.shelfmark
            )
            return

        footnote = Footnote.objects.create(
            source=source,
            content_object=doc,
            doc_relation=Footnote.EDITION,
        )
        LogEntry.objects.log_action(
            user_id=self.script_user.id,
            content_type_id=self.footnote_contenttype.pk,
            object_id=footnote.pk,
            object_repr=str(footnote),
            change_message="Created Goitein unpublished editions footnote to sync transcription",
            action_flag=ADDITION,
        )

        return footnote

    def sync_git(self, gitrepo_url, local_path):
        """ensure git repository has been cloned and content is up to date"""

        # if directory does not yet exist, clone repository
        if not os.path.isdir(local_path):
            if self.verbosity >= self.v_normal:
                self.stdout.write(
                    "Cloning TEI transcriptions repository to %s" % local_path
                )
            Repo.clone_from(url=gitrepo_url, to_path=local_path)
        else:
            # pull any changes since the last run
            Repo(local_path).remotes.origin.pull()

    def log_footnote_update(self, footnote, xmlfile):
        """create a log entry for a footnote that has been updated"""
        LogEntry.objects.log_action(
            user_id=self.script_user.id,
            content_type_id=self.footnote_contenttype.pk,
            object_id=footnote.pk,
            object_repr=str(footnote),
            change_message="Updated transcription from TEI file %s" % xmlfile,
            action_flag=CHANGE,
        )
