from django.conf import settings
from django.contrib.sites.models import Site


def absolutize_url(local_url, request=None):
    """Convert a local url to an absolute url, with scheme and server name,
    based on the current configured :class:`~django.contrib.sites.models.Site`.
    :param local_url: local url to be absolutized, e.g. something generated by
        :meth:`~django.urls.reverse`
    """
    # Borrowed from https://github.com/Princeton-CDH/mep-django/blob/main/mep/common/utils.py

    if local_url.startswith("https"):
        return local_url

    # add scheme and server (i.e., the http://example.com) based
    # on the django Sites infrastructure.
    root = Site.objects.get_current().domain
    # add http:// if necessary, since most sites docs
    # suggest using just the domain name
    if not root.startswith("http"):
        # if in debug mode and request is passed in, use
        # the current scheme (i.e. http for localhost/runserver)
        if settings.DEBUG and request:
            root = "%s://%s" % (request.scheme, root)
        # assume https for production sites
        else:
            root = "https://" + root

    # make sure there is no double slash between site url and local url
    if local_url.startswith("/"):
        root = root.rstrip("/")

    return root + local_url


def custom_tag_string(tag_string):
    """
    A custom tag string parser for taggit so that we can have multi-word
    tags. Django-taggit allows for multi-word tags, but TaggableManager does not
    encourage users to input them correctly.

    TaggableManager does not have an intuitive string output. If there are
    no tags, it will return a comma-delimited string. It will wrap existing
    tags in quotes. So if a user wants to add a tag "Arabic script" to a document
    with the existing tag "fiscal document" it will send the value:
    `"fiscal document", Arabic script` to be parsed.

    This is configured in settings with TAGGIT_TAGS_FROM_STRING.
    """
    # Stack overflow solution: https://stackoverflow.com/questions/30513783/django-taggit-how-to-allow-multi-word-tags

    return [t.strip(' "') for t in tag_string.split(",") if t.strip(' "')]
