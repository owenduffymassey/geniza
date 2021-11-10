from datetime import datetime

import pytest
from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.utils.timezone import get_current_timezone, make_aware

from geniza.corpus.models import Document, DocumentType, Fragment, TextBlock
from geniza.footnotes.models import Creator, Footnote, Source, SourceType


def make_fragment():
    """A real fragment from CUL, with URLs for testing."""
    return Fragment.objects.create(
        shelfmark="CUL Add.2586",
        url="https://cudl.lib.cam.ac.uk/view/MS-ADD-02586",
        iiif_url="https://cudl.lib.cam.ac.uk/iiif/MS-ADD-02586",
    )


def make_multifragment():
    """A real multifragment object, with fake URLs for testing."""
    return Fragment.objects.create(
        shelfmark="T-S 16.377",
        url="https://example.com/view/TS16.377",
        iiif_url="https://iiif.example.com/TS16.377",
        is_multifragment=True,
    )


def make_document(fragment):
    """A real legal document from the PGP."""
    doc = Document.objects.create(
        id=3951,
        description="""Deed of sale in which a father sells to his son a quarter
         of the apartment belonging to him in a house in the al- Mu'tamid
         passage of the Tujib quarter for seventeen dinars. Dated 1233.
         (Information from Mediterranean Society, IV, p. 281)""",
        doctype=DocumentType.objects.get_or_create(name="Legal")[0],
    )
    TextBlock.objects.create(document=doc, fragment=fragment)
    doc.tags.add("bill of sale", "real estate")
    dctype = ContentType.objects.get_for_model(Document)
    script_user = User.objects.get(username=settings.SCRIPT_USERNAME)
    team_user = User.objects.get(username=settings.TEAM_USERNAME)
    LogEntry.objects.create(
        user=team_user,
        object_id=str(doc.pk),
        object_repr=str(doc)[:200],
        content_type=dctype,
        change_message="Initial data entry (spreadsheet), dated 2004",
        action_flag=ADDITION,
        action_time=make_aware(
            datetime(year=2004, month=1, day=1), timezone=get_current_timezone()
        ),
    )
    LogEntry.objects.create(
        user=script_user,
        object_id=str(doc.pk),
        object_repr=str(doc)[:200],
        content_type=dctype,
        change_message="Imported via script",
        action_flag=ADDITION,
        action_time=make_aware(
            datetime(year=2021, month=5, day=3), timezone=get_current_timezone()
        ),
    )
    return doc


def make_document_with_editor():
    frag = Fragment.objects.create(
        shelfmark="T-S 99.999",
        is_multifragment=True,
    )
    doc = Document.objects.create(
        id=999999,
        description="""Lorem ipsum dolor sit amet, consectetur adipiscing elit,
        sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
        Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris
        nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in
        reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla
        pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa
        qui officia deserunt mollit anim id est laborum.""",
        doctype=DocumentType.objects.get_or_create(name="Legal")[0],
    )
    TextBlock.objects.create(document=doc, fragment=frag)
    doc.tags.add("bill of sale", "real estate")
    marina = Creator.objects.create(last_name="Rustow", first_name="Marina")
    book = SourceType.objects.create(type="Book")
    source = Source.objects.create(source_type=book)
    source.authors.add(marina)
    foot = Footnote.objects.create(
        doc_relation=[Footnote.EDITION],
        source=source,
        content_type_id=ContentType.objects.get(model="document").id,
        object_id=999999,
    )
    doc.footnotes.add(foot)
    return doc


def make_join(fragment, multifragment):
    """A fake letter document that occurs on two different fragments."""
    doc = Document.objects.create(
        description="testing description",
        doctype=DocumentType.objects.get_or_create(name="Letter")[0],
    )
    TextBlock.objects.create(document=doc, fragment=fragment, order=1)
    TextBlock.objects.create(document=doc, fragment=multifragment, order=2)
    return doc


@pytest.fixture
def fragment(db):
    return make_fragment()


@pytest.fixture
def multifragment(db):
    return make_multifragment()


@pytest.fixture
def document(db, fragment):
    return make_document(fragment)


@pytest.fixture
def join(db, fragment, multifragment):
    return make_join(fragment, multifragment)


@pytest.fixture
def document_with_editor(db):
    return make_document_with_editor()
