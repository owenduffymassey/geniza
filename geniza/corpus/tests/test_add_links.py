from collections import Counter, defaultdict
from io import StringIO
from unittest.mock import Mock, mock_open, patch
from urllib.parse import quote

import pytest
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.core.management import call_command
from django.core.management.base import CommandError

from geniza.corpus.management.commands import add_links
from geniza.corpus.models import Document
from geniza.footnotes.models import Footnote, Source, SourceType


@pytest.fixture
def jewish_traders(db):
    book_type = SourceType.objects.get(type="Book")
    # not the full record; just what is needed for testing this script
    return Source.objects.create(
        title="Letters of Medieval Jewish Traders", source_type=book_type
    )


@pytest.fixture
def india_book(db):
    book_type = SourceType.objects.get(type="Book")
    # not alll records; just enough to test this script
    return Source.objects.bulk_create(
        [
            Source(title="India Book 1", source_type=book_type),
            Source(title="India Book 2", source_type=book_type),
        ]
    )


@pytest.mark.django_db
@patch("geniza.corpus.management.commands.add_links.Command.setup", Mock())
class TestAddLinksSkipSetup:
    # all of these tests skip the command that requests authors and sources from the db

    @patch("geniza.corpus.management.commands.add_links.Command.add_link")
    def test_handle(self, mock_add_link):
        stdout = StringIO()
        command = add_links.Command(stdout=stdout)
        command.csv_path = "foo.csv"
        csv_data = "\n".join(
            [
                "object_id,link_type,link_target,link_title",
                "451,goitein_note,link_to_doc.pdf,goitein",
            ]
        )
        mockfile = mock_open(read_data=csv_data)

        # populate fields expected by summary
        command.stats = Counter()
        for stat in ["ignored", "errored", "document_not_found", "sources_created"]:
            command.stats[stat] = 0

        with patch("geniza.corpus.management.commands.add_links.open", mockfile):
            command.handle()
            mock_add_link.assert_called_with(
                {
                    "object_id": "451",
                    "link_type": "goitein_note",
                    "link_target": "link_to_doc.pdf",
                    "link_title": "goitein",
                }
            )

        # check summary output
        output = stdout.getvalue()
        assert "Created 0 new sources" in output
        assert "Created 0 new footnotes" in output

    def test_call_command(self):
        # test calling from command line; file not found on nonexistent csv
        with pytest.raises(CommandError):
            call_command("add_links", "nonexistent.csv")

    def test_handle_missing_csv_headers(self):
        command = add_links.Command(stdout=StringIO())
        # none of the headers match
        csv_data = "\n".join(["foo,bar,baz", "one,two,three"])
        mockfile = mock_open(read_data=csv_data)

        with patch("geniza.corpus.management.commands.add_links.open", mockfile):
            with pytest.raises(CommandError) as err:
                command.handle()
            assert "CSV is missing required fields" in str(err)

    def test_handle_file_not_found(self):
        command = add_links.Command(stdout=StringIO())
        with pytest.raises(CommandError) as err:
            command.handle(csv="/tmp/example/not-here.csv")
        assert "CSV file not found" in str(err)


def test_setup(typed_texts, jewish_traders, india_book):
    cmd = add_links.Command()
    cmd.setup()
    # check that contents are pulled as neded
    assert cmd.goitein
    assert cmd.goitein.last_name == "Goitein"
    assert cmd.unpublished
    assert cmd.unpublished == typed_texts.source_type

    assert cmd.jewish_traders
    assert cmd.jewish_traders == jewish_traders

    assert cmd.india_book
    assert cmd.india_book["India Book 1"] == india_book[0]
    assert cmd.india_book["India Book 2"] == india_book[1]

    assert cmd.script_user
    assert cmd.content_types


def test_get_goitein_source_existing(typed_texts, jewish_traders, india_book, document):
    cmd = add_links.Command()
    # typed text has volume CUL; document shelfmark starts CUL
    cmd.setup()

    source = cmd.get_goitein_source(document, "typed texts")
    assert source == typed_texts


def test_get_goitein_source_new(typed_texts, jewish_traders, india_book, multifragment):
    cmd = add_links.Command()
    # typed text has volume CUL; document shelfmark starts CUL
    cmd.setup()
    cmd.stats = {"sources_created": 0}
    # create document with T-S shelfmark
    doc = Document.objects.create()
    doc.fragments.add(multifragment)

    source = cmd.get_goitein_source(doc, "typed texts")
    # new source, not existing typed texts
    assert source != typed_texts
    assert source.volume == "T-S 16"
    assert cmd.stats["sources_created"] == 1
    # should create log entry documenting footnote creation
    log = LogEntry.objects.get(object_id=source.pk)
    assert log.action_flag == ADDITION


def test_get_india_book(typed_texts, jewish_traders, india_book):
    cmd = add_links.Command()
    cmd.setup()

    source = cmd.get_india_book("India Traders of the Middle Ages, II-11b")
    assert source.title == "India Book 2"
    assert source == india_book[1]


def test_set_footnote_url_create(typed_texts, jewish_traders, india_book, document):
    cmd = add_links.Command()
    cmd.setup()
    cmd.stats = {"footnotes_created": 0, "footnotes_updated": 0}

    test_url = "http://example.com/pgp/link/"
    footnote = cmd.set_footnote_url(
        document, jewish_traders, url=test_url, doc_relation=Footnote.TRANSLATION
    )
    assert footnote.content_object == document
    assert footnote.source == jewish_traders
    assert footnote.url == test_url
    assert footnote.doc_relation == Footnote.TRANSLATION
    assert cmd.stats["footnotes_created"] == 1
    # should create log entry documenting footnote creation
    log = LogEntry.objects.get(object_id=footnote.pk)
    assert log.action_flag == ADDITION
    assert log.change_message == "Created by add_links script"
    assert log.user_id == cmd.script_user.id

    # if we try to set a new url, should not update the same footnote
    second_url = "http://example.com/pgp/another-link/"
    second_footnote = cmd.set_footnote_url(
        document, jewish_traders, url=second_url, doc_relation=Footnote.TRANSLATION
    )
    assert cmd.stats["footnotes_created"] == 2
    assert second_footnote != footnote

    # testing updating footnote
    second_footnote.url = ""
    second_footnote.save()
    cmd.set_footnote_url(
        document, jewish_traders, url=second_url, doc_relation=Footnote.TRANSLATION
    )
    # a change entry should be created
    log = LogEntry.objects.get(object_id=second_footnote.pk, action_flag=CHANGE)
    assert log.change_message == "Updated by add_links script"


def test_set_footnote_url_update(typed_texts, jewish_traders, india_book, document):
    cmd = add_links.Command()
    cmd.setup()
    cmd.stats = {"footnotes_created": 0, "footnotes_updated": 0}

    # create a typed text footnote on document with no url to update
    existing_note = Footnote.objects.create(content_object=document, source=typed_texts)

    test_url = "http://example.com/pgp/link/"
    footnote = cmd.set_footnote_url(
        document, typed_texts, url=test_url, doc_relation=Footnote.EDITION
    )
    # should update the existing footnote
    assert footnote.pk == existing_note.pk
    assert footnote.url == test_url
    assert cmd.stats["footnotes_created"] == 0
    assert cmd.stats["footnotes_updated"] == 1


@patch("geniza.corpus.management.commands.add_links.Command.set_footnote_url")
def test_add_link(mock_set_footnote, typed_texts, jewish_traders, india_book, document):
    cmd = add_links.Command()
    cmd.link_type = None
    cmd.setup()
    cmd.stats = defaultdict(int)

    test_row = {
        "object_id": document.pk,
        "link_type": "jewish-traders",
        "link_target": "abc123",
    }
    cmd.add_link(test_row)
    mock_set_footnote.assert_called_with(
        doc=document,
        source=jewish_traders,
        url="https://s3.amazonaws.com/goitein-lmjt/abc123",
        doc_relation=Footnote.TRANSLATION,
    )

    test_row["link_type"] = "goitein_note"
    cmd.add_link(test_row)
    mock_set_footnote.assert_called_with(
        doc=document,
        source=typed_texts,
        url="https://commons.princeton.edu/media/geniza/abc123",
        doc_relation=Footnote.EDITION,
    )
    test_row["link_type"] = "indexcard"
    cmd.add_link(test_row)
    indexcard_source = cmd.get_goitein_source(
        doc=document,
        title="index cards",
    )
    mock_set_footnote.assert_called_with(
        doc=document,
        source=indexcard_source,
        url="https://geniza.princeton.edu/indexcards/"
        + quote("index.php?a=card&id=abc123"),
        doc_relation=Footnote.DISCUSSION,
    )
    test_row.update(
        {
            "link_type": "india-traders",
            "link_title": "India Traders of the Middle Ages, I-3",
        }
    )
    cmd.add_link(test_row)
    mock_set_footnote.assert_called_with(
        doc=document,
        source=india_book[0],
        url="https://s3.amazonaws.com/goitein-india-traders/abc123",
        doc_relation=Footnote.TRANSLATION,
    )


def test_add_link_ignored():
    cmd = add_links.Command()
    cmd.link_type = None
    assert cmd.add_link({"link_type": "transcription"}) == -1

    # specify single link type
    cmd.link_type = "jewish-traders"
    assert cmd.add_link({"link_type": "indexcard"}) == -1


# TODO: add & test log entry handling
