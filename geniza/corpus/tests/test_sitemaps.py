from datetime import date
from unittest.mock import patch

from django.urls import reverse
from parasolr.django import SolrClient

from geniza.corpus.models import Document
from geniza.corpus.sitemaps import DocumentScholarshipSitemap, DocumentSitemap
from geniza.corpus.tests.conftest import make_document
from geniza.footnotes.models import Footnote


class TestDocumentSitemap:
    def test_items(self, document, suppressed_document):
        # Ensure that documents are supressed if they aren't public
        assert document.status == Document.PUBLIC
        SolrClient().update.index(
            [document, suppressed_document],
            commit=True,
        )
        sitemap = DocumentSitemap()
        assert document.id in [obj["pgpid"] for obj in sitemap.items()]
        assert suppressed_document.id not in [obj["pgpid"] for obj in sitemap.items()]

    def test_location(self):
        assert DocumentSitemap().location(
            {"pgpid": "444", "last_modified": "2020-05-12T15:46:20.341Z"}
        ) == reverse("corpus:document", args=["444"])

    def test_lastmod(self):
        assert DocumentSitemap().lastmod(
            {"last_modified": "2020-05-12T15:46:20.341Z"}
        ) == date(2020, 5, 12)


class TestDocumentScholarshipSitemap:
    def test_items(self, document, source, suppressed_document, fragment):
        document_with_footnote = make_document(fragment, id=41)
        Footnote.objects.create(
            source=source,
            content_object=document_with_footnote,
            location="p.1",
            doc_relation=Footnote.EDITION,
        )

        SolrClient().update.index(
            [
                document.index_data(),  # no scholarship records
                suppressed_document.index_data(),  # suppressed
                document_with_footnote.index_data(),  # has scholarship
            ],
            commit=True,
        )

        # Ensure that only public documents with footnotes are returned
        sitemap = DocumentScholarshipSitemap()
        assert document_with_footnote.id in [obj["pgpid"] for obj in sitemap.items()]
        assert suppressed_document.id not in [obj["pgpid"] for obj in sitemap.items()]
        assert document.id not in [obj["pgpid"] for obj in sitemap.items()]

    def test_location(self, document, source):
        assert DocumentScholarshipSitemap().location(
            {"pgpid": "444", "last_modified": "2020-05-12T15:46:20.341Z"}
        ) == reverse("corpus:document-scholarship", args=["444"])

    def test_lastmod(self):
        assert DocumentScholarshipSitemap().lastmod(
            {"last_modified": "2020-05-12T15:46:20.341Z"}
        ) == date(2020, 5, 12)
