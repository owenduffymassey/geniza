from django.contrib import admin

from geniza.corpus.models import Collection, Fragment, \
    Document, DocumentType, LanguageScript, TextUnit


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ('abbrev', 'library', 'location', 'collection')
    search_fields = ('library', 'location', 'collection')


@admin.register(LanguageScript)
class LanguageScriptAdmin(admin.ModelAdmin):
    list_display = ('language', 'script', 'display_name')


class TextUnitInline(admin.TabularInline):
    model = TextUnit
    autocomplete_fields = ['fragment']
    # TODO: iiif viewer? can we adapt same embed from fragment page,
    # maybe as a widget


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        'shelfmark', 'description', 'doctype',
        'tag_list', 'all_languages', 'is_textblock',
        'last_modified'
    )
    readonly_fields = ('old_input_by', 'old_input_date',
                       'created', 'last_modified', 'shelfmark')
    search_fields = ('shelfmark', 'tag__name', 'description',
                     'old_input_by')  #  TODO search on edition when we add footnotes

    list_filter = (
        'doctype', 'languages', 'textunit__text_block',
    )

    fields = (
        'shelfmark',
        'doctype',
        'languages',
        'description',
        'tags',
        # edition, translation
        'notes',
        # text block
        ('old_input_by', 'old_input_date'),
        ('created', 'last_modified')
    )
    filter_horizontal = ('languages', )
    inlines = [
        TextUnitInline,
    ]

    def all_languages(self, doc):
        return ','.join([str(lang) for lang in doc.languages.all()])
    all_languages.short_description = 'Language'

    def get_queryset(self, request):
        return super().get_queryset(request) \
            .prefetch_related('tags', 'languages', 'fragments')

    def tag_list(self, obj):
        return ", ".join(o.name for o in obj.tags.all())
    tag_list.short_description = 'tags'


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(Fragment)
class FragmentAdmin(admin.ModelAdmin):
    list_display = ('shelfmark', 'collection', 'url',
                    'is_multifragment')
    search_fields = ('shelfmark', 'old_shelfmarks', 'notes')
    readonly_fields = ('old_shelfmarks', 'created', 'last_modified',)
    list_filter = (
        'collection',
        ('multifragment', admin.BooleanFieldListFilter),
        ('url', admin.BooleanFieldListFilter),
    )
    list_editable = ('url',)
    fields = (
        ('shelfmark', 'old_shelfmarks'),
        'collection',
        ('url', 'iiif_url'),
        'multifragment',
        'notes',
        ('created', 'last_modified')
    )
