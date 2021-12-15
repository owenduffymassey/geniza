import logging
from collections import defaultdict

from django.conf import settings
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models.functions import Concat
from django.db.models.functions.text import Lower
from django.db.models.query import Prefetch
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import activate
from django.utils.translation import gettext as _
from parasolr.django.indexing import ModelIndexable
from piffle.image import IIIFImageClient
from piffle.presentation import IIIFPresentation
from taggit.models import Tag
from taggit_selectize.managers import TaggableManager

from geniza.common.models import TrackChangesModel
from geniza.common.utils import absolutize_url
from geniza.footnotes.models import Creator, Footnote

logger = logging.getLogger(__name__)


class CollectionManager(models.Manager):
    def get_by_natural_key(self, name, library):
        return self.get(name=name, library=library)


class Collection(models.Model):
    """Collection or library that holds Geniza fragments"""

    library = models.CharField(max_length=255, blank=True)  # optional
    lib_abbrev = models.CharField("Library Abbreviation", max_length=255, blank=True)
    abbrev = models.CharField("Collection Abbreviation", max_length=255, blank=True)
    name = models.CharField(
        "Collection Name",
        max_length=255,
        blank=True,
        help_text="Collection name, if different than Library",
    )
    location = models.CharField(
        max_length=255, help_text="Current location of the collection", blank=True
    )

    objects = CollectionManager()

    class Meta:
        # sort on the combination of these fields, since many are optional
        # NOTE: this causes problems for sorting related models in django admin
        # (i.e., sorting fragments by collection); see corpus admin for workaround
        ordering = [
            Concat(
                models.F("lib_abbrev"),
                models.F("abbrev"),
                models.F("name"),
                models.F("library"),
            )
        ]
        constraints = [
            # require at least one of library OR name
            models.CheckConstraint(
                check=(models.Q(library__regex=".+") | models.Q(name__regex=".+")),
                name="req_library_or_name",
            ),
            models.UniqueConstraint(
                fields=["library", "name"], name="unique_library_name"
            ),
        ]

    def __str__(self):
        # by default, combine abbreviations
        values = [val for val in (self.lib_abbrev, self.abbrev) if val]
        # but abbreviations are optional, so fallback to names
        if not values:
            values = [val for val in (self.name, self.library) if val]
        return ", ".join(values)

    def natural_key(self):
        return (self.name, self.library)


class LanguageScriptManager(models.Manager):
    def get_by_natural_key(self, language, script):
        return self.get(language=language, script=script)


class LanguageScript(models.Model):
    """Combination language and script"""

    language = models.CharField(max_length=255)
    script = models.CharField(max_length=255)
    display_name = models.CharField(
        max_length=255,
        blank=True,
        unique=True,
        null=True,
        help_text="Option to override the autogenerated language-script name",
    )
    iso_code = models.CharField(
        "ISO Code",
        max_length=3,
        blank=True,
        help_text="ISO 639 code for this language (2 or 3 letters)",
    )

    objects = LanguageScriptManager()

    class Meta:
        verbose_name = "Language + Script"
        verbose_name_plural = "Languages + Scripts"
        ordering = ["language"]
        constraints = [
            models.UniqueConstraint(
                fields=["language", "script"], name="unique_language_script"
            )
        ]

    def __str__(self):
        # Allow display_name to override autogenerated string
        # otherwise combine language and script
        #   e.g. Judaeo-Arabic (Hebrew script)
        return self.display_name or f"{self.language} ({self.script} script)"

    def natural_key(self):
        return (self.language, self.script)


class FragmentManager(models.Manager):
    def get_by_natural_key(self, shelfmark):
        return self.get(shelfmark=shelfmark)


class Fragment(TrackChangesModel):
    """A single fragment or multifragment held by a
    particular library or archive."""

    shelfmark = models.CharField(max_length=255, unique=True)
    # multiple, semicolon-delimited values. Keeping as single-valued for now
    old_shelfmarks = models.CharField(
        "Historical Shelfmarks",
        blank=True,
        max_length=500,
        help_text="Semicolon-delimited list of previously used shelfmarks; "
        + "automatically updated on shelfmark change.",
    )
    collection = models.ForeignKey(
        Collection, blank=True, on_delete=models.SET_NULL, null=True
    )
    url = models.URLField(
        "URL", blank=True, help_text="Link to library catalog record for this fragment."
    )
    iiif_url = models.URLField("IIIF URL", blank=True)
    is_multifragment = models.BooleanField(
        "Multifragment",
        default=False,
        help_text="True if there are multiple fragments in one shelfmark",
    )
    notes = models.TextField(blank=True)
    needs_review = models.TextField(
        blank=True,
        help_text="Enter text here if an administrator needs to review this fragment.",
    )

    created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    objects = FragmentManager()

    # NOTE: may want to add optional ForeignKey to djiffy Manifest here
    # (or property to find by URI if not an actual FK)

    class Meta:
        ordering = ["shelfmark"]

    def __str__(self):
        return self.shelfmark

    def natural_key(self):
        return (self.shelfmark,)

    def iiif_images(self):
        # if there is no iiif for this fragment, bail out
        if not self.iiif_url:
            return None
        images = []
        labels = []
        manifest = IIIFPresentation.from_url(self.iiif_url)
        for canvas in manifest.sequences[0].canvases:
            image_id = canvas.images[0].resource.id
            images.append(IIIFImageClient(*image_id.rsplit("/", 1)))
            # label provides library's recto/verso designation
            labels.append(canvas.label)

        return images, labels

    def iiif_thumbnails(self):
        # if there are no iiif images for this fragment, bail out
        iiif_images = self.iiif_images()
        if iiif_images is None:
            return ""

        images, labels = iiif_images
        return mark_safe(
            " ".join(
                # include label as title for now
                '<img src="%s" loading="lazy" height="200" title="%s">'
                % (img.size(height=200), labels[i])
                for i, img in enumerate(images)
            )
        )

    def save(self, *args, **kwargs):
        """Remember how shelfmarks have changed by keeping a semi-colon list
        in the old_shelfmarks field"""
        if self.pk and self.has_changed("shelfmark"):
            if self.old_shelfmarks:
                old_shelfmarks = set(self.old_shelfmarks.split(";"))
                old_shelfmarks.add(self.initial_value("shelfmark"))
                self.old_shelfmarks = ";".join(old_shelfmarks - {self.shelfmark})
            else:
                self.old_shelfmarks = self.initial_value("shelfmark")

        # NOTE: consider triggering manifest import here when iiif url changes

        super(Fragment, self).save(*args, **kwargs)


class DocumentTypeManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(name=name)


class DocumentType(models.Model):
    """The category of document in question."""

    name = models.CharField(max_length=255, unique=True)
    display_label = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional label for display on the public site",
    )

    objects = DocumentTypeManager()

    def __str__(self):
        return self.display_label or self.name

    def natural_key(self):
        return (self.name,)


class DocumentSignalHandlers:
    """Signal handlers for indexing :class:`Document` records when
    related records are saved or deleted."""

    # lookup from model verbose name to attribute on documents
    # for use in queryset filter
    model_filter = {
        "fragment": "fragments",
        "tag": "tags",
        "document type": "doctype",
        "Related Fragment": "textblock",  # textblock verbose name
    }

    @staticmethod
    def related_change(instance, raw, mode):
        """reindex all associated documents when related data is changed"""
        # common logic for save and delete
        # raw = saved as presented; don't query the database
        if raw or not instance.pk:
            return
        # get related lookup for document filter
        model_name = instance._meta.verbose_name
        doc_attr = DocumentSignalHandlers.model_filter.get(model_name)
        # if handler fired on an model we don't care about, warn and exit
        if not doc_attr:
            logger.warning(
                "Indexing triggered on %s but no document attribute is configured"
                % model_name
            )
            return

        doc_filter = {"%s__pk" % doc_attr: instance.pk}
        docs = Document.items_to_index().filter(**doc_filter)
        if docs.exists():
            logger.debug(
                "%s %s, reindexing %d related document(s)",
                model_name,
                mode,
                docs.count(),
            )
            ModelIndexable.index_items(docs)

    @staticmethod
    def related_save(sender, instance=None, raw=False, **_kwargs):
        # delegate to common method
        DocumentSignalHandlers.related_change(instance, raw, "save")

    @staticmethod
    def related_delete(sender, instance=None, raw=False, **_kwargs):
        # delegate to common method
        DocumentSignalHandlers.related_change(instance, raw, "delete")


class Document(ModelIndexable):
    """A unified document such as a letter or legal document that
    appears on one or more fragments."""

    id = models.AutoField("PGPID", primary_key=True)
    fragments = models.ManyToManyField(
        Fragment, through="TextBlock", related_name="documents"
    )
    description = models.TextField(blank=True)
    doctype = models.ForeignKey(
        DocumentType,
        blank=True,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Type",
        help_text='Refer to <a href="%s" target="_blank">PGP Document Type Guide</a>'
        % settings.PGP_DOCTYPE_GUIDE,
    )
    tags = TaggableManager(blank=True, related_name="tagged_document")
    languages = models.ManyToManyField(
        LanguageScript, blank=True, verbose_name="Primary Languages"
    )
    secondary_languages = models.ManyToManyField(
        LanguageScript, blank=True, related_name="secondary_document"
    )
    language_note = models.TextField(
        blank=True, help_text="Notes on diacritics, vocalisation, etc."
    )
    notes = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    needs_review = models.TextField(
        blank=True,
        help_text="Enter text here if an administrator needs to review this document.",
    )
    old_pgpids = ArrayField(models.IntegerField(), null=True, verbose_name="Old PGPIDs")

    PUBLIC = "P"
    SUPPRESSED = "S"
    STATUS_CHOICES = (
        (PUBLIC, "Public"),
        (SUPPRESSED, "Suppressed"),
    )
    #: status of record; currently choices are public or suppressed
    status = models.CharField(
        max_length=2,
        choices=STATUS_CHOICES,
        default=PUBLIC,
        help_text="Decide whether a document should be publicly visible",
    )

    # preliminary date fields so dates can be pulled out from descriptions
    doc_date_original = models.CharField(
        "Date on document (original)",
        help_text="explicit date on the document, in original format",
        blank=True,
        max_length=255,
    )
    CALENDAR_HIJRI = "h"
    CALENDAR_KHARAJI = "k"
    CALENDAR_SELEUCID = "s"
    CALENDAR_ANNOMUNDI = "am"
    CALENDAR_CHOICES = (
        (CALENDAR_HIJRI, "Hijrī"),
        (CALENDAR_KHARAJI, "Kharājī"),
        (CALENDAR_SELEUCID, "Seleucid"),
        (CALENDAR_ANNOMUNDI, "Anno Mundi"),
    )
    doc_date_calendar = models.CharField(
        "Calendar",
        max_length=2,
        choices=CALENDAR_CHOICES,
        help_text="Calendar according to which the document gives a date: "
        + "Hijrī (AH); Kharājī (rare - mostly for fiscal docs); "
        + "Seleucid (sometimes listed as Minyan Shetarot); Anno Mundi (Hebrew calendar)",
        blank=True,
    )
    doc_date_standard = models.CharField(
        "Document date (standardized)",
        help_text="CE date (convert to Julian before 1582, Gregorian after 1582). "
        + "Use YYYY, YYYY-MM, YYYY-MM-DD format when possible",
        blank=True,
        max_length=255,
    )

    footnotes = GenericRelation(Footnote, related_query_name="document")
    log_entries = GenericRelation(LogEntry, related_query_name="document")

    # NOTE: default ordering disabled for now because it results in duplicates
    # in django admin; see admin for ArrayAgg sorting solution
    class Meta:
        pass
        # abstract = False
        # ordering = [Least('textblock__fragment__shelfmark')]

    def __str__(self):
        return f"{self.shelfmark_display or '??'} (PGPID {self.id or '??'})"

    @staticmethod
    def get_by_any_pgpid(pgpid):
        """Find a document by current or old pgpid"""
        return Document.objects.filter(
            models.Q(id=pgpid) | models.Q(old_pgpids__contains=[pgpid])
        ).first()

    @property
    def shelfmark(self):
        """shelfmarks for associated fragments"""
        # access via textblock so we follow specified order,
        # use dict keys to ensure unique
        return " + ".join(
            dict.fromkeys(
                block.fragment.shelfmark
                for block in self.textblock_set.all()
                if block.certain  # filter locally instead of in the db
            )
        )

    @property
    def shelfmark_display(self):
        """First shelfmark plus join indicator for shorter display."""
        # NOTE preliminary pending more discussion and implementation of #154:
        # https://github.com/Princeton-CDH/geniza/issues/154
        certain = list(
            dict.fromkeys(
                block.fragment.shelfmark
                for block in self.textblock_set.filter(certain=True)
            ).keys()
        )
        if not certain:
            return None
        return certain[0] + (" + …" if len(certain) > 1 else "")

    @property
    def collection(self):
        """collection (abbreviation) for associated fragments"""
        # use set to ensure unique; sort for reliable output order
        return ", ".join(
            sorted(
                set(
                    [
                        block.fragment.collection.abbrev
                        for block in self.textblock_set.all()
                        if block.fragment.collection
                    ]
                )
            )
        )

    def all_languages(self):
        return ", ".join([str(lang) for lang in self.languages.all()])

    all_languages.short_description = "Language"

    def all_secondary_languages(self):
        return ",".join([str(lang) for lang in self.secondary_languages.all()])

    all_secondary_languages.short_description = "Secondary Language"

    def all_tags(self):
        return ", ".join(t.name for t in self.tags.all())

    all_tags.short_description = "tags"

    def alphabetized_tags(self):
        return self.tags.order_by(Lower("name"))

    def is_public(self):
        """admin display field indicating if doc is public or suppressed"""
        return self.status == self.PUBLIC

    is_public.short_description = "Public"
    is_public.boolean = True
    is_public.admin_order_field = "status"

    def get_absolute_url(self):
        return reverse("corpus:document", args=[str(self.id)])

    @property
    def permalink(self):
        # generate permalink without language url so that all versions
        # have the same link and users will be directed preferred language
        activate("en")
        return absolutize_url(self.get_absolute_url().replace("/en/", "/"))

    def iiif_urls(self):
        """List of IIIF urls for images of the Document's Fragments."""
        return list(
            dict.fromkeys(
                filter(None, [b.fragment.iiif_url for b in self.textblock_set.all()])
            )
        )

    def fragment_urls(self):
        """List of external URLs to view the Document's Fragments."""
        return list(
            dict.fromkeys(
                filter(None, [b.fragment.url for b in self.textblock_set.all()])
            )
        )

    def has_transcription(self):
        """Admin display field indicating if document has a transcription."""
        return any(note.has_transcription() for note in self.footnotes.all())

    has_transcription.short_description = "Transcription"
    has_transcription.boolean = True
    has_transcription.admin_order_field = "footnotes__content"

    def has_image(self):
        """Admin display field indicating if document has a IIIF image."""
        return any(self.iiif_urls())

    has_image.short_description = "Image"
    has_image.boolean = True
    has_image.admin_order_field = "textblock__fragment__iiif_url"

    @property
    def title(self):
        """Short title for identifying the document, e.g. via search."""
        return f"{self.doctype or _('Unknown type')}: {self.shelfmark_display or '??'}"

    def editions(self):
        """All footnotes for this document where the document relation includes
        edition; footnotes with content will be sorted first."""
        return self.footnotes.filter(doc_relation__contains=Footnote.EDITION).order_by(
            "content", "source"
        )

    def digital_editions(self):
        """All footnotes for this document where the document relation includes
        edition AND the footnote has content."""
        return (
            self.footnotes.filter(doc_relation__contains=Footnote.EDITION)
            .filter(content__isnull=False)
            .order_by("content", "source")
        )

    def editors(self):
        """All unique authors of digital editions for this document."""
        return Creator.objects.filter(
            source__footnote__doc_relation__contains=Footnote.EDITION,
            source__footnote__content__isnull=False,
            source__footnote__document=self,
        ).distinct()

    @classmethod
    def items_to_index(cls):
        """Custom logic for finding items to be indexed when indexing in
        bulk."""
        # TODO: can we share common/reused prefetching logic
        # in a custom qureyset filter or similar? (adapted here from admin)
        return cls.objects.select_related("doctype").prefetch_related(
            "tags",
            "languages",
            "footnotes",
            "log_entries",
            Prefetch(
                "textblock_set",
                queryset=TextBlock.objects.select_related(
                    "fragment", "fragment__collection"
                ),
            ),
        )

    def index_data(self):
        """data for indexing in Solr"""
        index_data = super().index_data()

        # get fragments via textblocks for correct order
        # and to take advantage of prefetching
        fragments = [tb.fragment for tb in self.textblock_set.all()]
        index_data.update(
            {
                "pgpid_i": self.id,
                "type_s": str(self.doctype) if self.doctype else _("Unknown type"),
                "description_t": self.description,
                "notes_t": self.notes or None,
                "needs_review_t": self.needs_review or None,
                "shelfmark_ss": [f.shelfmark for f in fragments],
                # library/collection possibly redundant?
                "collection_ss": [str(f.collection) for f in fragments],
                "tags_ss": [t.name for t in self.tags.all()],
                "status_s": self.get_status_display(),
                "old_pgpids_is": self.old_pgpids,
                "language_code_ss": [lang.iso_code for lang in self.languages.all()],
            }
        )

        # count scholarship records by type
        footnotes = self.footnotes.all()
        counts = defaultdict(int)
        transcription_texts = []
        for fn in footnotes:
            for val in fn.doc_relation:
                counts[val] += 1
            # if this is an edition/transcription, try to get plain text for indexing
            if Footnote.EDITION in fn.doc_relation and fn.content:
                plaintext = fn.content_text()
                if plaintext:
                    transcription_texts.append(plaintext)

        index_data.update(
            {
                "num_editions_i": counts[Footnote.EDITION],
                "num_translations_i": counts[Footnote.TRANSLATION],
                "num_discussions_i": counts[Footnote.DISCUSSION],
                "scholarship_count_i": sum(counts.values()),
                # preliminary scholarship record indexing
                # (may need splitting out and weighting based on type of scholarship)
                "scholarship_t": [fn.display() for fn in footnotes],
                # text content of any transcriptions
                "transcription_t": transcription_texts,
            }
        )

        last_log_entry = self.log_entries.last()
        if last_log_entry:
            index_data["input_year_i"] = last_log_entry.action_time.year
            # TODO: would be nice to use full date to display year
            # instead of indexing separately
            # (may require parasolr datetime conversion support? or implement
            # in local queryset?)
            index_data[
                "input_date_dt"
            ] = last_log_entry.action_time.isoformat().replace("+00:00", "Z")

        return index_data

    # define signal handlers to update the index based on changes
    # to other models
    index_depends_on = {
        "fragments": {
            "post_save": DocumentSignalHandlers.related_save,
            "pre_delete": DocumentSignalHandlers.related_delete,
        },
        "tags": {
            "post_save": DocumentSignalHandlers.related_save,
            "pre_delete": DocumentSignalHandlers.related_delete,
        },
        "doctype": {
            "post_save": DocumentSignalHandlers.related_save,
            "pre_delete": DocumentSignalHandlers.related_delete,
        },
        "textblock_set": {
            "post_save": DocumentSignalHandlers.related_save,
            "pre_delete": DocumentSignalHandlers.related_delete,
        }
        # footnotes and sources, when we include editors/translators
        # script+language when/if included in index data
    }

    def merge_with(self, merge_docs, rationale, user=None):
        """Merge the specified documents into this one. Combines all
        metadata into this document, adds the merged documents into
        list of old PGP IDs, and creates a log entry documenting
        the merge, including the rationale."""

        # initialize old pgpid list if previously unset
        if self.old_pgpids is None:
            self.old_pgpids = []

        # if user is not specified, log entry will be associated with
        # script and document will be flagged for review
        script = False
        if user is None:
            user = User.objects.get(username=settings.SCRIPT_USERNAME)
            script = True

        description_chunks = [self.description]
        language_notes = [self.language_note] if self.language_note else []
        notes = [self.notes] if self.notes else []
        needs_review = [self.needs_review] if self.needs_review else []

        for doc in merge_docs:
            # add merge id to old pgpid list
            self.old_pgpids.append(doc.id)
            # add any tags from merge document tags to primary doc
            self.tags.add(*doc.tags.names())
            # add description if set and not duplicated
            if doc.description and doc.description not in self.description:
                description_chunks.append(
                    "Description from PGPID %s:\n%s" % (doc.id, doc.description)
                )
            # add any notes
            if doc.notes:
                notes.append("Notes from PGPID %s:\n%s" % (doc.id, doc.notes))
            if doc.needs_review:
                needs_review.append(doc.needs_review)

            # add languages and secondary languages
            for lang in doc.languages.all():
                self.languages.add(lang)
            for lang in doc.secondary_languages.all():
                self.secondary_languages.add(lang)
            if doc.language_note:
                language_notes.append(doc.language_note)

            # if there are any textblocks with fragments not already
            # asociated with this document, reassociate
            # (i.e., for newly discovered joins)
            # does not deal with discrepancies between text block fields or order
            for textblock in doc.textblock_set.all():
                if textblock.fragment not in self.fragments.all():
                    self.textblock_set.add(textblock)

            self._merge_footnotes(doc)
            self._merge_logentries(doc)

        # combine text fields
        self.description = "\n".join(description_chunks)
        self.notes = "\n".join(notes)
        self.language_note = "; ".join(language_notes)
        # if merged via script, flag for review
        if script:
            needs_review.insert(0, "SCRIPTMERGE")
        self.needs_review = "\n".join(needs_review)

        # save current document with changes; delete merged documents
        self.save()
        merged_ids = ", ".join([str(doc.id) for doc in merge_docs])
        for doc in merge_docs:
            doc.delete()
        # create log entry documenting the merge; include rationale
        doc_contenttype = ContentType.objects.get_for_model(Document)
        LogEntry.objects.log_action(
            user_id=user.id,
            content_type_id=doc_contenttype.pk,
            object_id=self.pk,
            object_repr=str(self),
            change_message="merged with %s: %s" % (merged_ids, rationale),
            action_flag=CHANGE,
        )

    def _merge_footnotes(self, doc):
        # combine footnotes; footnote logic for merge_with
        for footnote in doc.footnotes.all():
            # first, check for an exact match
            equiv_fn = self.footnotes.includes_footnote(footnote)
            # if there is no exact match, check again ignoring content
            if not equiv_fn:
                equiv_fn = self.footnotes.includes_footnote(
                    footnote, include_content=False
                )
                # if there's a partial match (everything but content)
                if equiv_fn:
                    # if the new footnote has content, add it
                    if footnote.content:
                        self.footnotes.add(footnote)
                    # if the partial match has no content, remove it
                    # (if it has any content, then it is different from the new one
                    # and should be preserved)
                    if not equiv_fn.content:
                        self.footnotes.remove(equiv_fn)

                # if neither an exact or partial match, add the new footnote
                else:
                    self.footnotes.add(footnote)

    def _merge_logentries(self, doc):
        # reassociate log entries; logic for merge_with
        # make a list of currently associated log entries to skip duplicates
        current_logs = [
            "%s_%s" % (le.user_id, le.action_time.isoformat())
            for le in self.log_entries.all()
        ]
        for log_entry in doc.log_entries.all():
            # check duplicate log entries, based on user id and time
            # (likely only applies to historic input & revision)
            if (
                "%s_%s" % (log_entry.user_id, log_entry.action_time.isoformat())
                in current_logs
            ):
                # skip if it's a duplicate
                continue

            # otherwise annotate and reassociate
            # - modify change message to document which object this event applied to
            log_entry.change_message = "%s [PGPID %d]" % (
                log_entry.change_message,
                doc.pk,
            )
            log_entry.save()
            # - associate with the primary document
            self.log_entries.add(log_entry)


class TextBlock(models.Model):
    """The portion of a document that appears on a particular fragment."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    fragment = models.ForeignKey(Fragment, on_delete=models.CASCADE)
    certain = models.BooleanField(
        default=True,
        help_text=(
            "Are you certain that this fragment belongs to this document? "
            + "Uncheck this box if you are uncertain of a potential join."
        ),
    )
    RECTO = "r"
    VERSO = "v"
    RECTO_VERSO = "rv"
    RECTO_VERSO_CHOICES = [
        (RECTO, "recto"),
        (VERSO, "verso"),
        (RECTO_VERSO, "recto and verso"),
    ]
    side = models.CharField(blank=True, max_length=5, choices=RECTO_VERSO_CHOICES)
    region = models.CharField(
        blank=True,
        max_length=255,
        help_text="Label for region of fragment that document text occupies",
    )
    multifragment = models.CharField(
        max_length=255,
        blank=True,
        help_text="Identifier for fragment part, if part of a multifragment",
    )
    order = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Order with respect to other text blocks in this document, "
        + "top to bottom or right to left",
    )

    class Meta:
        ordering = ["order"]
        verbose_name = "Related Fragment"  # for researcher legibility in admin

    def __str__(self):
        # combine shelfmark, multifragment, side, region, and certainty
        certainty_str = "(?)" if not self.certain else ""
        parts = [
            self.fragment.shelfmark,
            self.multifragment,
            self.get_side_display(),
            self.region,
            certainty_str,
        ]
        return " ".join(p for p in parts if p)

    def thumbnail(self):
        return self.fragment.iiif_thumbnails()
