from time import sleep
from unittest import mock
from unittest.mock import Mock, mock_open, patch

import pytest
from django.db.models.fields import related
from django.http.response import Http404
from django.urls import reverse
from django.utils.text import Truncator, slugify
from parasolr.django import SolrClient
from pytest_django.asserts import assertContains, assertNotContains

from geniza.common.utils import absolutize_url
from geniza.corpus.iiif_utils import EMPTY_CANVAS_ID, new_iiif_canvas
from geniza.corpus.models import Document, DocumentType, Fragment, TextBlock
from geniza.corpus.solr_queryset import DocumentSolrQuerySet
from geniza.corpus.views import (
    DocumentAnnotationListView,
    DocumentDetailView,
    DocumentManifestView,
    DocumentScholarshipView,
    DocumentSearchView,
    DocumentTranscriptionText,
    old_pgp_edition,
    old_pgp_tabulate_data,
    pgp_metadata_for_old_site,
)
from geniza.footnotes.models import Creator, Footnote, Source, SourceType


class TestDocumentDetailView:
    def test_page_title(self, document, client):
        """should use doc title as detail view meta title"""
        response = client.get(reverse("corpus:document", args=(document.id,)))
        assert response.context["page_title"] == document.title

    def test_page_description(self, document, client):
        """should use truncated doc description as detail view meta description"""
        response = client.get(reverse("corpus:document", args=(document.id,)))
        assert response.context["page_description"] == Truncator(
            document.description
        ).words(20)

    def test_get_queryset(self, db, client):
        # Ensure page works normally when not suppressed
        doc = Document.objects.create()
        response = client.get(doc.get_absolute_url())
        assert response.status_code == 200
        assertContains(response, "shelfmark")

        # Test that when status isn't public, it is suppressed
        doc = Document.objects.create(status=Document.SUPPRESSED)
        response = client.get(doc.get_absolute_url())
        assert response.status_code == 404

    def test_permalink(self, document, client):
        """should contain permalink generated from absolutize_url"""
        response = client.get(reverse("corpus:document", args=(document.id,)))
        permalink = absolutize_url(document.get_absolute_url()).replace("/en/", "/")
        assertContains(response, f'<link rel="canonical" href="{permalink}"')

    def test_past_id_mixin(self, db, client):
        """should redirect from 404 to new pgpid when an old_pgpid is matched"""
        response_404 = client.get(reverse("corpus:document", args=(2,)))
        assert response_404.status_code == 404
        doc = Document.objects.create(id=1, old_pgpids=[2])
        response_301 = client.get(reverse("corpus:document", args=(2,)))
        assert response_301.status_code == 301
        assert response_301.url == absolutize_url(doc.get_absolute_url())

        # Test when pgpid not first in the list
        response_404_notfirst = client.get(reverse("corpus:document", args=(71,)))
        assert response_404_notfirst.status_code == 404
        doc.old_pgpids = [5, 6, 71]
        doc.save()
        response_301_notfirst = client.get(reverse("corpus:document", args=(71,)))
        assert response_301_notfirst.status_code == 301
        assert response_301_notfirst.url == absolutize_url(doc.get_absolute_url())

        # Test partial matching pgpid
        response_404_partialmatch = client.get(reverse("corpus:document", args=(7,)))
        assert response_404_partialmatch.status_code == 404

    def test_get_absolute_url(self, document):
        """should return doc permalink"""
        doc_detail_view = DocumentDetailView()
        doc_detail_view.object = document
        doc_detail_view.kwargs = {"pk": document.pk}
        assert doc_detail_view.get_absolute_url() == absolutize_url(
            document.get_absolute_url()
        )


@pytest.mark.django_db
def test_old_pgp_tabulate_data():
    legal_doc, _ = DocumentType.objects.get_or_create(name="Legal")
    doc = Document.objects.create(id=36, doctype=legal_doc)
    frag = Fragment.objects.create(shelfmark="T-S 8J22.21")
    TextBlock.objects.create(document=doc, fragment=frag, side="r")
    doc.fragments.add(frag)
    doc.tags.add("marriage")

    table_iter = old_pgp_tabulate_data(Document.objects.all())
    row = next(table_iter)

    assert "T-S 8J22.21" in row
    assert "#marriage" in row
    assert "recto" in row
    # should not error on document with no old pgpids

    # NOTE: strings are not parsed until after being fed into the csv plugin
    assert legal_doc in row
    assert 36 in row

    doc.old_pgpids = [12345, 67890]
    doc.save()
    table_iter = old_pgp_tabulate_data(Document.objects.all())
    row = next(table_iter)
    assert "12345;67890" in row


@pytest.mark.django_db
def test_old_pgp_edition():
    # Expected behavior:
    # Ed. [fn].
    # Ed. [fn]; also ed. [fn].
    # Ed. [fn]; also ed. [fn]; also trans. [fn].
    # Ed. [fn] [url]; also ed. [fn]; also trans. [fn].

    doc = Document.objects.create()
    assert old_pgp_edition(doc.editions()) == ""

    marina = Creator.objects.create(last_name="Rustow", first_name="Marina")
    book = SourceType.objects.create(type="Book")
    source = Source.objects.create(source_type=book)
    source.authors.add(marina)
    fn = Footnote.objects.create(
        doc_relation=[Footnote.EDITION],
        source=source,
        content_object=doc,
    )
    doc.footnotes.add(fn)

    edition_str = old_pgp_edition(doc.editions())
    assert edition_str == f"Ed. {fn.display()}"

    source2 = Source.objects.create(title="Arabic dictionary", source_type=book)
    fn2 = Footnote.objects.create(
        doc_relation=[Footnote.EDITION],
        source=source2,
        content_object=doc,
    )
    doc.footnotes.add(fn2)
    edition_str = old_pgp_edition(doc.editions())
    assert edition_str == f"Ed. Arabic dictionary; also ed. Marina Rustow."

    source3 = Source.objects.create(title="Geniza Encyclopedia", source_type=book)
    fn_trans = Footnote.objects.create(
        doc_relation=[Footnote.EDITION, Footnote.TRANSLATION],
        source=source3,
        content_object=doc,
    )
    doc.footnotes.add(fn_trans)
    edition_str = old_pgp_edition(doc.editions())
    assert (
        edition_str
        == "Ed. Arabic dictionary; also ed. and trans. Geniza Encyclopedia; also ed. Marina Rustow."
    )

    fn.url = "example.com"
    fn.save()
    edition_str = old_pgp_edition(doc.editions())
    assert (
        edition_str
        == "Ed. Arabic dictionary; also ed. and trans. Geniza Encyclopedia; also ed. Marina Rustow example.com."
    )


@pytest.mark.django_db
def test_pgp_metadata_for_old_site():
    legal_doc, _ = DocumentType.objects.get_or_create(name="Legal")
    doc = Document.objects.create(id=36, doctype=legal_doc)
    frag = Fragment.objects.create(shelfmark="T-S 8J22.21")
    TextBlock.objects.create(document=doc, fragment=frag, side="r")
    doc.fragments.add(frag)
    doc.tags.add("marriage")

    doc2 = Document.objects.create(status=Document.SUPPRESSED)

    response = pgp_metadata_for_old_site(Mock())
    assert response.status_code == 200

    streaming_content = response.streaming_content
    header = next(streaming_content)
    row1 = next(streaming_content)

    # Ensure no suppressed documents are published
    with pytest.raises(StopIteration):
        row2 = next(streaming_content)

    # Ensure objects have been correctly parsed as strings
    assert b"36" in row1
    assert b"Legal" in row1


class TestDocumentSearchView:
    def test_ignore_suppressed_documents(self, document, empty_solr):
        suppressed_document = Document.objects.create(status=Document.SUPPRESSED)
        Document.index_items([document, suppressed_document])
        SolrClient().update.index([], commit=True)
        # [d.index_data() for d in [document, suppressed_document]], commit=True
        # )
        print(suppressed_document.index_data())

        docsearch_view = DocumentSearchView()
        # mock request with empty keyword search
        docsearch_view.request = Mock()
        docsearch_view.request.GET = {"q": ""}
        qs = docsearch_view.get_queryset()
        result_pgpids = [obj["pgpid"] for obj in qs]
        print(result_pgpids)
        print(qs)
        assert qs.count() == 1
        assert document.id in result_pgpids
        assert suppressed_document.id not in result_pgpids

    def test_get_form_kwargs(self):
        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()
        # no params
        docsearch_view.request.GET = {}
        assert docsearch_view.get_form_kwargs() == {
            "initial": {
                "sort": "scholarship_desc",
            },
            "prefix": None,
            "data": {"sort": "scholarship_desc"},
        }

        # keyword search param
        docsearch_view.request.GET = {"q": "contract"}
        assert docsearch_view.get_form_kwargs() == {
            "initial": {"sort": "scholarship_desc"},
            "prefix": None,
            "data": {
                "q": "contract",
                "sort": "relevance",
            },
        }

        # sort search param
        docsearch_view.request.GET = {"sort": "scholarship_desc"}
        assert docsearch_view.get_form_kwargs() == {
            "initial": {
                "sort": "scholarship_desc",
            },
            "prefix": None,
            "data": {
                "sort": "scholarship_desc",
            },
        }

        # keyword and sort search params
        docsearch_view.request.GET = {"q": "contract", "sort": "scholarship_desc"}
        assert docsearch_view.get_form_kwargs() == {
            "initial": {
                "sort": "scholarship_desc",
            },
            "prefix": None,
            "data": {
                "q": "contract",
                "sort": "scholarship_desc",
            },
        }

    @pytest.mark.usefixtures("mock_solr_queryset")
    def test_get_queryset(self, mock_solr_queryset):
        with patch(
            "geniza.corpus.views.DocumentSolrQuerySet",
            new=self.mock_solr_queryset(
                DocumentSolrQuerySet, extra_methods=["admin_search", "keyword_search"]
            ),
        ) as mock_queryset_cls:

            docsearch_view = DocumentSearchView()
            docsearch_view.request = Mock()

            # keyword search param
            docsearch_view.request.GET = {"q": "six apartments"}
            qs = docsearch_view.get_queryset()

            mock_queryset_cls.assert_called_with()
            mock_sqs = mock_queryset_cls.return_value
            mock_sqs.keyword_search.assert_called_with("six apartments")
            mock_sqs.keyword_search.return_value.highlight.assert_any_call(
                "description", snippets=3, method="unified", requireFieldMatch=True
            )
            mock_sqs.also.assert_called_with("score")
            mock_sqs.also.return_value.order_by.assert_called_with("-score")

            # sort search param
            mock_sqs.reset_mock()
            docsearch_view.request = Mock()
            docsearch_view.request.GET = {"sort": "relevance"}
            qs = docsearch_view.get_queryset()
            mock_sqs = mock_queryset_cls.return_value
            mock_sqs.keyword_search.assert_not_called()
            # filter called once to limit by status
            assert mock_sqs.filter.call_count == 1
            mock_sqs.filter.assert_called_with(status=Document.STATUS_PUBLIC)
            mock_sqs.order_by.assert_called_with("-score")

            # keyword, sort, and doctype filter search params
            mock_sqs.reset_mock()
            docsearch_view.request = Mock()
            docsearch_view.request.GET = {
                "q": "six apartments",
                "sort": "scholarship_desc",
                "doctype": ["Legal"],
            }
            qs = docsearch_view.get_queryset()
            mock_sqs = mock_queryset_cls.return_value
            mock_sqs.keyword_search.assert_called_with("six apartments")
            mock_sqs.keyword_search.return_value.also.return_value.order_by.return_value.filter.assert_called()
            mock_sqs.keyword_search.return_value.also.return_value.order_by.assert_called_with(
                "-scholarship_count_i"
            )

            # empty params
            mock_sqs.reset_mock()
            docsearch_view.request = Mock()
            docsearch_view.request.GET = {"q": "", "sort": ""}
            qs = docsearch_view.get_queryset()
            mock_sqs = mock_queryset_cls.return_value
            mock_sqs.keyword_search.assert_not_called()
            mock_sqs.order_by.assert_called_with("-scholarship_count_i")

            # no params
            mock_sqs.reset_mock()
            docsearch_view.request = Mock()
            docsearch_view.request.GET = {}
            qs = docsearch_view.get_queryset()
            mock_sqs = mock_queryset_cls.return_value
            mock_sqs.keyword_search.assert_not_called()
            mock_sqs.order_by.assert_called_with("-scholarship_count_i")

    @pytest.mark.usefixtures("mock_solr_queryset")
    @patch("geniza.corpus.views.DocumentSearchView.get_queryset")
    def test_get_context_data(self, mock_get_queryset, rf, mock_solr_queryset):
        with patch(
            "geniza.corpus.views.DocumentSolrQuerySet",
            new=mock_solr_queryset(
                DocumentSolrQuerySet, extra_methods=["admin_search", "keyword_search"]
            ),
        ) as mock_queryset_cls:

            mock_qs = mock_queryset_cls.return_value
            mock_qs.count.return_value = 22
            mock_qs.get_facets.return_value.facet_fields = {}
            # mock_qs.__getitem__.return_value = docsearch_view.queryset

            mock_get_queryset.return_value = mock_qs

            docsearch_view = DocumentSearchView(kwargs={})
            docsearch_view.queryset = mock_qs
            docsearch_view.object_list = mock_qs
            docsearch_view.request = rf.get("/documents/")

            context_data = docsearch_view.get_context_data()
            assert (
                context_data["highlighting"]
                == context_data["page_obj"].object_list.get_highlighting.return_value
            )
            assert context_data["page_obj"].start_index() == 0
            # NOTE: test paginator isn't initialized properly from queryset count
            # assert context_data["paginator"].count == 22

    def test_scholarship_sort(
        self,
        document,
        join,
        empty_solr,
        source,
        twoauthor_source,
        multiauthor_untitledsource,
    ):
        """integration test for sorting by scholarship asc and desc"""

        Footnote.objects.create(
            content_object=join,
            source=source,
            doc_relation=Footnote.EDITION,
        )
        doc_three_records = Document.objects.create(
            description="testing description",
        )
        for src in [source, twoauthor_source, multiauthor_untitledsource]:
            Footnote.objects.create(
                content_object=doc_three_records,
                source=src,
                doc_relation=Footnote.EDITION,
            )

        # ensure solr index is updated with all three test documents
        SolrClient().update.index(
            [
                document.index_data(),  # no scholarship records
                join.index_data(),  # one scholarship record
                doc_three_records.index_data(),  # 3 scholarship records
            ],
            commit=True,
        )
        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()

        # no sort, no query
        docsearch_view.request.GET = {}
        qs = docsearch_view.get_queryset()
        # should return all three documents
        assert qs.count() == 3
        # by default, should return document with most records first
        assert (
            qs[0]["pgpid"] == doc_three_records.id
        ), "document with most scholarship records returned first"

        # sort by scholarship desc
        docsearch_view.request.GET = {"sort": "scholarship_desc"}
        qs = docsearch_view.get_queryset()
        # should return document with most records first
        assert (
            qs[0]["pgpid"] == doc_three_records.id
        ), "document with most scholarship records returned first"

        # sort by scholarship asc
        docsearch_view.request.GET = {"sort": "scholarship_asc"}
        qs = docsearch_view.get_queryset()
        # should return document with fewest records first
        assert (
            qs[0]["pgpid"] == document.id
        ), "document with fewest scholarship records returned first"

        # sort by scholarship asc with query
        docsearch_view.request.GET = {"sort": "scholarship_asc", "q": "testing"}
        qs = docsearch_view.get_queryset()
        # should return 2 documents
        assert qs.count() == 2
        # should return document with fewest records first
        assert (
            qs[0]["pgpid"] == join.id
        ), "document with matching description and fewest scholarship records returned first"

    def test_doctype_filter(self, document, join, empty_solr):
        """Integration test for document type filter"""
        SolrClient().update.index(
            [
                document.index_data(),  # type = Legal document
                join.index_data(),  # type = Letter
            ],
            commit=True,
        )
        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()

        # no filter
        docsearch_view.request.GET = {}
        qs = docsearch_view.get_queryset()
        assert qs.count() == 2

        # filter by doctype "Legal document"
        docsearch_view.request.GET = {"doctype": ["Legal document"]}
        qs = docsearch_view.get_queryset()
        assert qs.count() == 1
        assert qs[0]["pgpid"] == document.id, "Only legal document returned"

    def test_shelfmark_boost(self, empty_solr, document, multifragment):
        # integration test for shelfmark field boosting
        # in solr configuration
        # - using empty solr fixture to ensure solr is empty when this test starts

        # create a second document with a different shelfmark
        # that references the shelfmark of the first in the description
        related_doc = Document.objects.create(
            description="See also %s" % document.shelfmark
        )
        TextBlock.objects.create(document=related_doc, fragment=multifragment)

        # third document with similar shelfmark
        frag = Fragment.objects.create(
            shelfmark="CUL Add.300",  # fixture has shelfmark CUL Add.2586
        )
        neighbor_doc = Document.objects.create()
        TextBlock.objects.create(document=neighbor_doc, fragment=frag)
        # ensure solr index is updated with all three test documents
        SolrClient().update.index(
            [
                document.index_data(),
                neighbor_doc.index_data(),
                related_doc.index_data(),
            ],
            commit=True,
        )

        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()
        # assuming relevance sort is default; update if that changes
        docsearch_view.request.GET = {"q": document.shelfmark, "sort": "relevance"}
        qs = docsearch_view.get_queryset()
        # should return all three documents
        assert qs.count() == 3
        # document with exact match on shelfmark should be returned first
        assert (
            qs[0]["pgpid"] == document.id
        ), "document with matching shelfmark returned first"
        # document with full shelfmark should in description should be second
        assert (
            qs[1]["pgpid"] == related_doc.id
        ), "document with shelfmark in description returned second"
        # (document with similar shelfmark is third)


class TestDocumentScholarshipView:
    def test_page_title(self, document, client, source):
        """should incorporate doc title into scholarship page title"""
        Footnote.objects.create(content_object=document, source=source)
        response = client.get(
            reverse("corpus:document-scholarship", args=(document.id,))
        )
        assert response.context["page_title"] == f"Scholarship on {document.title}"

    def test_page_description(self, document, client, source):
        """should use number of scholarship records as scholarship page description"""
        Footnote.objects.create(content_object=document, source=source)
        response = client.get(
            reverse("corpus:document-scholarship", args=(document.id,))
        )
        assert (
            response.context["page_description"]
            == f"1 scholarship record for {document.title}"
        )

    def test_get_queryset(self, client, document, source):
        # no footnotes; should 404
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assert response.status_code == 404

        # add a footnote; should return document in context
        Footnote.objects.create(content_object=document, source=source)
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assert response.context["document"] == document

        # suppress document; should 404 again
        document.status = Document.SUPPRESSED
        document.save()
        response = client.get(
            reverse("corpus:document-scholarship", args=[document.pk])
        )
        assert response.status_code == 404

    def test_past_id_mixin(self, db, client, source):
        """should redirect from 404 to new pgpid when an old_pgpid is matched"""
        response_404 = client.get(reverse("corpus:document-scholarship", args=[2]))
        assert response_404.status_code == 404
        doc = Document.objects.create(id=1, old_pgpids=[2])
        Footnote.objects.create(content_object=doc, source=source)
        response_301 = client.get(reverse("corpus:document-scholarship", args=[2]))
        assert response_301.status_code == 301
        assert response_301.url == absolutize_url(
            f"{doc.get_absolute_url()}scholarship/"
        )

    def test_get_absolute_url(self, document, source):
        """should return scholarship permalink"""
        Footnote.objects.create(content_object=document, source=source)
        doc_detail_view = DocumentScholarshipView()
        doc_detail_view.object = document
        doc_detail_view.kwargs = {"pk": document.pk}
        assert doc_detail_view.get_absolute_url() == absolutize_url(
            f"{document.get_absolute_url()}scholarship/"
        )

    def test_get_paginate_by(self):
        """Should set pagination to 2 per page"""
        docsearch_view = DocumentSearchView(kwargs={})
        docsearch_view.request = Mock()
        docsearch_view.request.GET = {"per_page": "2"}
        qs = docsearch_view.get_queryset()
        assert docsearch_view.get_paginate_by(qs) == 2


@patch("geniza.corpus.views.IIIFPresentation")
class TestDocumentManifestView:
    view_name = "corpus:document-manifest"

    def test_no_images_no_transcription(
        self, mockiifpres, client, document, source, fragment
    ):
        # fixture document fragment has iiif, so remove it to test
        fragment.iiif_url = ""
        fragment.save()
        # no iiif or transcription; should 404
        response = client.get(reverse(self.view_name, args=[document.pk]))
        assert response.status_code == 404

    def test_images_no_transcription(
        self, mockiifpres, client, document, source, fragment
    ):
        # document fragment has iiif, but no transcription; should return a manifest

        mock_manifest = mockiifpres.from_url.return_value
        mock_manifest.label = "Remote content"
        mock_manifest.id = "http://example.io/manifest/1"
        mock_manifest.attribution = (
            "Metadata is public domain; restrictions apply to images."
        )
        mock_manifest.sequences = [
            Mock(canvases=[{"@type": "sc:Canvas", "@id": "urn:m1/c1"}])
        ]

        response = client.get(reverse(self.view_name, args=[document.pk]))
        assert response.status_code == 200

        assert mockiifpres.from_url.called_with(fragment.iiif_url)

        # should not contain annotation list, since there is no transcription
        assertNotContains(response, "otherContent")
        assertNotContains(response, "sc:AnnotationList")
        # inspect the result as json
        result = response.json()
        assert "Compilation by Princeton Geniza Project." in result["attribution"]
        assert "Additional restrictions may apply." in result["attribution"]
        assert mock_manifest.attribution in result["attribution"]
        # includes canvas from remote manifest
        canvas_1 = result["sequences"][0]["canvases"][0]
        assert canvas_1["@id"] == "urn:m1/c1"
        # includes provenance for canvas
        assert canvas_1["partOf"][0]["@id"] == mock_manifest.id
        assert (
            canvas_1["partOf"][0]["label"]["en"][0]
            == "original source: %s" % mock_manifest.label
        )

    def test_no_images_transcription(
        self, mockiifpres, client, document, source, fragment
    ):
        # remove iiif url from fixture document fragment has iiif
        fragment.iiif_url = ""
        fragment.save()
        # add a footnote with transcription content
        Footnote.objects.create(
            content_object=document,
            source=source,
            content={"html": "text"},
            doc_relation=Footnote.EDITION,
        )
        response = client.get(reverse(self.view_name, args=[document.pk]))
        assert response.status_code == 200

        # should not load any remote manifests
        assert mockiifpres.from_url.call_count == 0
        # should use empty canvas id
        assertContains(response, EMPTY_CANVAS_ID)
        # should include annotations
        assertContains(response, "otherContent")
        assertContains(response, "sc:AnnotationList")
        # includes url for annotation list
        assertContains(
            response, reverse("corpus:document-annotations", args=[document.pk])
        )

    def test_get_absolute_url(self, mockiifpres, document, source):
        """should return manifest permalink"""

        view = DocumentManifestView()
        view.object = document
        view.kwargs = {"pk": document.pk}
        assert view.get_absolute_url() == absolutize_url(
            f"{document.get_absolute_url()}iiif/manifest/"
        )


@patch("geniza.corpus.views.IIIFPresentation")
class TestDocumentAnnotationListView:
    view_name = DocumentAnnotationListView.viewname

    def test_no_transcription(self, mockiifpres, client, document):
        # no iiif or transcription; should 404
        response = client.get(reverse(self.view_name, args=[document.pk]))
        assert response.status_code == 404

    def test_images_transcription(
        self, mockiifpres, client, document, source, fragment
    ):
        # add a footnote with transcription content
        transcription = Footnote.objects.create(
            content_object=document,
            source=source,
            content={"html": "text"},
            doc_relation=Footnote.EDITION,
        )
        mock_manifest = mockiifpres.from_url.return_value
        test_canvas = new_iiif_canvas()
        test_canvas.id = "urn:m1/c1"
        test_canvas.width = 300
        test_canvas.height = 250
        mock_manifest.sequences = [Mock(canvases=[test_canvas])]
        annotation_list_url = reverse(self.view_name, args=[document.pk])
        response = client.get(annotation_list_url)
        assert response.status_code == 200
        # inspect result
        data = response.json()
        # each annotation should have a unique id based on annotation list & sequence
        assert data["resources"][0]["@id"].endswith("%s#1" % annotation_list_url)
        # annotation should be attached to canvas by uri with full width & height
        assert data["resources"][0]["on"] == "urn:m1/c1#xywh=0,0,300,250"
        assert (
            data["resources"][0]["resource"] == transcription.iiif_annotation_content()
        )

    def test_no_images_transcription(
        self, mockiifpres, client, document, source, fragment
    ):
        # remove iiif url from fixture document fragment has iiif
        fragment.iiif_url = ""
        fragment.save()
        # add a footnote with transcription content
        Footnote.objects.create(
            content_object=document,
            source=source,
            content={"html": "here is my transcription text"},
            doc_relation=Footnote.EDITION,
        )
        response = client.get(reverse(self.view_name, args=[document.pk]))
        assert response.status_code == 200

        # should not load any remote manifests
        assert mockiifpres.from_url.call_count == 0
        # should use empty canvas id
        assertContains(response, EMPTY_CANVAS_ID)
        # should include transcription content
        assertContains(response, "here is my transcription text")

    def test_no_shared_resources(
        self, mockiifpres, client, document, source, fragment, join
    ):
        # a list object initialized once in iiif_utils.base_annotation_list
        # was getting reused, resulting in annotations being aggregated
        # and kept every time annotation lists were generated

        # test to confirm the fix

        # remove iiif url from fragment fixture
        fragment.iiif_url = ""
        fragment.save()
        # add a footnote with transcription content to document
        Footnote.objects.create(
            content_object=document,
            source=source,
            content={"html": "here is my transcription text"},
            doc_relation=Footnote.EDITION,
        )
        # and another to the join document
        Footnote.objects.create(
            content_object=join,
            source=source,
            content={"html": "here is completely different transcription text"},
            doc_relation=Footnote.EDITION,
        )
        # request once for document
        client.get(reverse(self.view_name, args=[document.pk]))
        # then request for join doc
        response = client.get(reverse(self.view_name, args=[join.pk]))

        assertNotContains(response, "here is my transcription text")
        assertContains(response, "completely different transcription text")


@pytest.mark.django_db
class TestDocumentTranscriptionText:
    view_name = DocumentTranscriptionText.viewname

    def test_nonexesistent_pgpid(self, client):
        # non-existent pgpid should 404
        assert (
            client.get(
                reverse(self.view_name, kwargs={"pk": 123, "transcription_pk": 456})
            ).status_code
            == 404
        )

    def test_nonexesistent_footnote_id(self, client, document):
        # valid pgpid but non-existent footnote id should 404
        assert (
            client.get(
                reverse(
                    self.view_name, kwargs={"pk": document.pk, "transcription_pk": 123}
                )
            ).status_code
            == 404
        )

    def test_not_edition(self, client, document, source):
        # valid pgpid, valid footnote, but not an edition should 404
        discussion = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.DISCUSSION,
        )
        assert (
            client.get(
                reverse(
                    self.view_name,
                    kwargs={"pk": document.pk, "transcription_pk": discussion.pk},
                )
            ).status_code
            == 404
        )

    def test_no_content(self, client, document, source):
        # valid pgpid, valid footnote, but not an edition should 404
        edition = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.EDITION,
        )
        assert (
            client.get(
                reverse(
                    self.view_name,
                    kwargs={"pk": document.pk, "transcription_pk": edition.pk},
                )
            ).status_code
            == 404
        )

    def test_success(self, client, document, source):
        # valid pgpid, valid footnote, but not an edition should 404
        edition = Footnote.objects.create(
            content_object=document,
            source=source,
            doc_relation=Footnote.EDITION,
            content={
                "html": "some transcription text",
                "text": "some transcription text",
            },
        )
        response = client.get(
            reverse(
                self.view_name,
                kwargs={"pk": document.pk, "transcription_pk": edition.pk},
            )
        )
        assert response.status_code == 200
        assert response.headers["Content-Type"] == "text/plain; charset=UTF-8"
        content_disposition = response.headers["Content-Disposition"]
        assert content_disposition.startswith("attachment; filename=")
        assert content_disposition.endswith('.txt"')
        # check filename format
        filename = content_disposition.split("=")[1]
        # filename is wrapped in quotes; includes pgpid, shelfmark, author last name
        assert filename.startswith('"PGP%d' % document.pk)
        assert slugify(document.shelfmark) in filename
        assert slugify(source.authorship_set.first().creator.last_name) in filename

        assert response.content == b"some transcription text"
