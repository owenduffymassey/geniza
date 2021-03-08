from django.db import models
from django.utils.safestring import mark_safe
from piffle.image import IIIFImageClient
from piffle.presentation import IIIFPresentation
from taggit.managers import TaggableManager


class CollectionManager(models.Manager):

    def get_by_natural_key(self, abbrev):
        return self.get(abbrev=abbrev)


class Collection(models.Model):
    '''Collection at a library that holds Geniza fragments'''
    library = models.CharField(max_length=255)
    abbrev = models.CharField('Abbreviation', max_length=255)
    collection = models.CharField(
        max_length=255, blank=True,
        help_text='Collection name, if different than Library')
    location = models.CharField(
        max_length=255, help_text='Current location of the collection')

    objects = CollectionManager()

    class Meta:
        ordering = ['abbrev']
        constraints = [
            models.UniqueConstraint(fields=['library', 'collection'],
                                    name='unique_library_collection')
        ]

    def __str__(self):
        return self.abbrev

    def natural_key(self):
        return (self.abbrev, )


class LanguageScriptManager(models.Manager):

    def get_by_natural_key(self, language, script):
        return self.get(language=language, script=script)


class LanguageScript(models.Model):
    '''Combination language and script'''
    language = models.CharField(max_length=255)
    script = models.CharField(max_length=255)
    display_name = models.CharField(
        max_length=255, blank=True, unique=True, null=True,
        help_text="Option to override the autogenerated language-script name")

    objects = LanguageScriptManager()

    class Meta:
        verbose_name = 'Language + Script'
        verbose_name_plural = 'Languages + Scripts'
        ordering = ['language']
        constraints = [
            models.UniqueConstraint(fields=['language', 'script'],
                                    name='unique_language_script')
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


class Fragment(models.Model):
    '''A single fragment or multifragment held by a
    particular library or archive.'''
    shelfmark = models.CharField(max_length=255, unique=True)
    # multiple, semicolon-delimited values. Keeping as single-valued for now
    old_shelfmarks = models.CharField(
        'Historical Shelfmarks',
        max_length=255, blank=True)
    collection = models.ForeignKey(Collection, blank=True,
                                   on_delete=models.SET_NULL, null=True)
    url = models.URLField(
        'URL', blank=True,
        help_text="Link to library catalog record for this fragment.")
    iiif_url = models.URLField('IIIF URL', blank=True)
    multifragment = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    objects = FragmentManager()

    def __str__(self):
        return self.shelfmark

    def natural_key(self):
        return (self.shelfmark, )

    def is_multifragment(self):
        return bool(self.multifragment)
    is_multifragment.short_description = 'Multifragment?'
    is_multifragment.boolean = True

    def iiif_thumbnails(self):
        # if there is no iiif for this fragment, bail out
        if not self.iiif_url:
            return ''

        images = []
        labels = []
        manifest = IIIFPresentation.from_url(self.iiif_url)
        for canvas in manifest.sequences[0].canvases:
            image_id = canvas.images[0].resource.id
            images.append(IIIFImageClient(*image_id.rsplit('/', 1)))
            # label provides library's recto/verso designation
            labels.append(canvas.label)

        return mark_safe(' '.join(
            # include label as title for now
            '<img src="%s" loading="lazy" height="200" title="%s">' %
            (img.size(height=200), labels[i])
            for i, img in enumerate(images)
        ))


class DocumentType(models.Model):
    '''The category of document in question.'''
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class Document(models.Model):
    '''A unified document such as a letter or legal document that
    appears on one or more fragments.'''
    id = models.AutoField('PGPID', primary_key=True)
    fragments = models.ManyToManyField(Fragment, through='TextBlock')
    description = models.TextField(blank=True)
    doctype = models.ForeignKey(
        DocumentType, blank=True, on_delete=models.SET_NULL, null=True,
        verbose_name='Type')
    tags = TaggableManager(blank=True)
    languages = models.ManyToManyField(LanguageScript, blank=True)
    probable_languages = models.ManyToManyField(
        LanguageScript, blank=True, related_name='probable_document',
        limit_choices_to=~models.Q(language__exact='Unknown'))
    language_note = models.TextField(
        blank=True, help_text='Notes on diacritics, vocalisation, etc.')
    # TODO footnotes for edition/translation
    notes = models.TextField(blank=True)
    old_input_by = models.CharField(
        'Legacy input by', max_length=255,
        help_text='Legacy input information from Google Sheets')
    old_input_date = models.CharField(
        'Legacy input date', max_length=255,
        help_text='Legacy input date from Google Sheets')
    created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['fragments__shelfmark']

    def __str__(self):
        return self.shelfmark

    @property
    def shelfmark(self):
        '''shelfmarks for associated fragments'''
        # access via textblock so we follow specified order
        return ' + '.join([block.fragment.shelfmark
                           for block in self.textblock_set.all()])

    @property
    def collection(self):
        '''collection (abbreviation) for associated fragments'''
        # use set to ensure unique; sort for reliable output order
        return ', '.join(sorted(set([block.fragment.collection.abbrev for
                                block in self.textblock_set.all()
                                if block.fragment.collection])))

    def is_textblock(self):
        '''Is this document part of a notated text block?'''
        return any(bool(block.extent_label)
                   for block in self.textblock_set.all())
    is_textblock.short_description = 'Text Block?'
    is_textblock.boolean = True

    def all_languages(self):
        return ','.join([str(lang) for lang in self.languages.all()])
    all_languages.short_description = 'Language'

    def tag_list(self):
        return ", ".join(t.name for t in self.tags.all())
    tag_list.short_description = 'tags'


class TextBlock(models.Model):
    '''The portion of a document that appears on a particular fragment.'''
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    fragment = models.ForeignKey(Fragment, on_delete=models.CASCADE)
    RECTO = 'r'
    VERSO = 'v'
    RECTO_VERSO = 'rv'
    RECTO_VERSO_CHOICES = [
        (RECTO, 'recto'),
        (VERSO, 'verso'),
        (RECTO_VERSO, 'recto and verso'),
    ]
    side = models.CharField(blank=True, max_length=5,
                            choices=RECTO_VERSO_CHOICES)
    extent_label = models.CharField(blank=True, max_length=255)
    order = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Order if there are multiple fragments. ' +
                  'Top to bottom or right to left.')

    class Meta:
        ordering = ['order']

    def __str__(self):
        # combine shelfmark, side, and optionally text block
        parts = [self.fragment.shelfmark, self.get_side_display(),
                 self.extent_label]
        return ' '.join(p for p in parts if p)

    def thumbnail(self):
        return self.fragment.iiif_thumbnails()
