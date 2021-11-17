from time import sleep
from unittest import mock
from unittest.mock import Mock, patch

import pytest
from django.db.models.fields import related
from django.http.response import Http404
from django.urls import reverse
from django.utils.text import Truncator
from parasolr.django import SolrClient
from pytest_django.asserts import assertContains

from geniza.common.utils import absolutize_url
from geniza.corpus.models import Document, DocumentType, Fragment, TextBlock
from geniza.corpus.solr_queryset import DocumentSolrQuerySet
from geniza.corpus.views import (
    DocumentDetailView,
    DocumentScholarshipView,
    DocumentSearchView,
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
    def test_get_form_kwargs(self):
        docsearch_view = DocumentSearchView()
        docsearch_view.request = Mock()
        # no params
        docsearch_view.request.GET = {}
        assert docsearch_view.get_form_kwargs() == {
            "initial": {"sort": "scholarship_desc"},
            "prefix": None,
            "data": {"sort": "scholarship_desc"},
        }

        # keyword search param
        docsearch_view.request.GET = {"q": "contract"}
        assert docsearch_view.get_form_kwargs() == {
            "initial": {"sort": "scholarship_desc"},
            "prefix": None,
            "data": {"q": "contract", "sort": "relevance"},
        }

        # sort search param
        docsearch_view.request.GET = {"sort": "scholarship_desc"}
        assert docsearch_view.get_form_kwargs() == {
            "initial": {"sort": "scholarship_desc"},
            "prefix": None,
            "data": {"sort": "scholarship_desc"},
        }

        # keyword and sort search params
        docsearch_view.request.GET = {"q": "contract", "sort": "scholarship_desc"}
        assert docsearch_view.get_form_kwargs() == {
            "initial": {"sort": "scholarship_desc"},
            "prefix": None,
            "data": {"q": "contract", "sort": "scholarship_desc"},
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
            mock_sqs.keyword_search.return_value.highlight.assert_called_with(
                "description", snippets=3, method="unified"
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
            mock_sqs.order_by.assert_called_with("-score")

            # keyword and sort search params
            mock_sqs.reset_mock()
            docsearch_view.request = Mock()
            docsearch_view.request.GET = {
                "q": "six apartments",
                "sort": "scholarship_desc",
            }
            qs = docsearch_view.get_queryset()
            mock_sqs = mock_queryset_cls.return_value
            mock_sqs.keyword_search.assert_called_with("six apartments")
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
    def test_get_context_data(self, rf, mock_solr_queryset):
        with patch(
            "geniza.corpus.views.DocumentSolrQuerySet",
            new=mock_solr_queryset(
                DocumentSolrQuerySet, extra_methods=["admin_search", "keyword_search"]
            ),
        ) as mock_queryset_cls:
            docsearch_view = DocumentSearchView(kwargs={})
            docsearch_view.request = rf.get("/documents/")
            docsearch_view.queryset = mock_queryset_cls.return_value
            docsearch_view.queryset.count.return_value = 22
            docsearch_view.queryset.__getitem__.return_value = docsearch_view.queryset
            docsearch_view.object_list = docsearch_view.queryset

            context_data = docsearch_view.get_context_data()
            assert context_data["total"] == 22
            assert (
                context_data["highlighting"]
                == docsearch_view.queryset.get_highlighting.return_value
            )
            assert context_data["page_obj"].start_index() == 0

    def test_scholarship_sort(self, document, join, empty_solr, source):
        """integration test for sorting by scholarship asc and desc"""

        Footnote.objects.create(
            content_object=join,
            source=source,
            doc_relation=Footnote.EDITION,
        )
        doc_three_records = Document.objects.create(
            description="testing description",
        )
        for _ in range(3):
            Footnote.objects.create(
                content_object=doc_three_records,
                source=source,
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
