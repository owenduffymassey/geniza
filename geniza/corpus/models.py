import logging

from django.db import models
from django.urls import reverse
from django.db.models.functions import Concat, Coalesce
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import ArrayField
from django.utils.safestring import mark_safe
from piffle.image import IIIFImageClient
from piffle.presentation import IIIFPresentation
from taggit.models import Tag
from taggit_selectize.managers import TaggableManager
from parasolr.django.indexing import ModelIndexable

from geniza.footnotes.models import Footnote
from geniza.common.models import TrackChangesModel


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

    class Meta:
        ordering = ["shelfmark"]

    def __str__(self):
        return self.shelfmark

    def natural_key(self):
        return (self.shelfmark,)

    def iiif_thumbnails(self):
        # if there is no iiif for this fragment, bail out
        if not self.iiif_url:
            return ""

        images = []
        labels = []
        manifest = IIIFPresentation.from_url(self.iiif_url)
        for canvas in manifest.sequences[0].canvases:
            image_id = canvas.images[0].resource.id
            images.append(IIIFImageClient(*image_id.rsplit("/", 1)))
            # label provides library's recto/verso designation
            labels.append(canvas.label)

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
        super(Fragment, self).save(*args, **kwargs)


class DocumentType(models.Model):
    """The category of document in question."""

    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class DocumentSignalHandlers:
    """Signal handlers for indexing :class:`Document` records when
    related records are saved or deleted."""

    # lookup from model verbose name to attribute on documents
    # for use in queryset filter
    model_filter = {
        "fragment": "fragments",
        "tag": "tags",
        "document type": "doctype",
        # log entry ?
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
        # if handler fired on an model we don't care about, ignore
        if not doc_attr:
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
    )
    tags = TaggableManager(blank=True)
    languages = models.ManyToManyField(LanguageScript, blank=True)
    probable_languages = models.ManyToManyField(
        LanguageScript,
        blank=True,
        related_name="probable_document",
        limit_choices_to=~models.Q(language__exact="Unknown"),
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
    old_pgpids = ArrayField(models.IntegerField(), null=True)

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

    def all_probable_languages(self):
        return ",".join([str(lang) for lang in self.probable_languages.all()])

    all_probable_languages.short_description = "Probable Language"

    def all_tags(self):
        return ", ".join(t.name for t in self.tags.all())

    all_tags.short_description = "tags"

    def is_public(self):
        """admin display field indicating if doc is public or suppressed"""
        return self.status == self.PUBLIC

    is_public.short_description = "Public"
    is_public.boolean = True
    is_public.admin_order_field = "status"

    def get_absolute_url(self):
        return reverse("corpus:document", args=[str(self.id)])

    def iiif_urls(self):
        """List of IIIF urls for images of the Document's Fragments."""
        return list(
            dict.fromkeys(
                filter(None, [b.fragment.iiif_url for b in self.textblock_set.all()])
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
        return f"{self.doctype or 'Unknown'}: {self.shelfmark_display or '??'}"

    def editions(self):
        """All footnotes for this document where the document relation includes
        edition; footnotes with content will be sorted first."""
        return self.footnotes.filter(doc_relation__contains=Footnote.EDITION).order_by(
            "content", "source"
        )

    @classmethod
    def items_to_index(cls):
        """Custom logic for finding items to be indexed when indexing in
        bulk; only include public docs."""
        return cls.objects.filter(status=Document.PUBLIC)

    def index_data(self):
        """data for indexing in Solr"""

        index_data = super().index_data()
        index_data.update(
            {
                "pgpid_i": self.id,
                "type_s": self.doctype.name if self.doctype else "Unknown",
                "description_t": self.description,
                "notes_t": self.notes,
                "needs_review_t": self.needs_review,
                "shelfmark_ss": [f.shelfmark for f in self.fragments.all()],
                "tags_ss": [t.name for t in self.tags.all()],
                "status_s": self.get_status_display(),
                "old_pgpids_is": self.old_pgpids,
                # TODO: editors/translators/sources
            }
        )

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
        }
        # footnotes and sources, when we include editors/translators
        # script+language when/if included in index data
    }


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
    subfragment = models.CharField(
        max_length=255,
        blank=True,
        help_text="Identifier for subfragment, if part of a multifragment",
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
        # combine shelfmark, subfragment, side, region, and certainty
        certainty_str = "(?)" if not self.certain else ""
        parts = [
            self.fragment.shelfmark,
            self.subfragment,
            self.get_side_display(),
            self.region,
            certainty_str,
        ]
        return " ".join(p for p in parts if p)

    def thumbnail(self):
        return self.fragment.iiif_thumbnails()
