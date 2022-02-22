"""
Django settings for geniza project.

Generated by 'django-admin startproject' using Django 3.1.6.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""

from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.1/howto/deployment/checklist/

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Application definition

INSTALLED_APPS = [
    "modeltranslation",  # this has to come before admin config
    "wagtail.documents",  # this also has to come first to unregister
    "wagtail.images",  #    this also has to come first to unregister
    "geniza.apps.GenizaAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.humanize",
    "django.contrib.sessions",
    "django.contrib.messages",
    "geniza.apps.GenizaStaticFilesConfig",
    "django.contrib.postgres",
    "django.contrib.sites",
    "django_cas_ng",
    "taggit",
    "taggit_selectize",
    "pucas",
    "multiselectfield",
    "adminsortable2",
    "admin_log_entries",
    "parasolr",
    "webpack_loader",
    "csp_helpers",
    "djiffy",
    "widget_tweaks",
    "geniza.common",
    "geniza.corpus.apps.CorpusAppConfig",
    "geniza.footnotes.apps.FootnotesConfig",
    "geniza.pages.apps.PagesConfig",
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.admin",
    "wagtail.core",
    "wagtail_localize",
    "wagtail_localize.locales",
    "modelcluster",
    "django.contrib.sitemaps",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "geniza.common.middleware.PublicLocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # "csp.middleware.CSPMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

ROOT_URLCONF = "geniza.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "geniza" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "geniza.context_extras",
                "geniza.context_processors.template_globals",
            ],
        },
    },
]

WSGI_APPLICATION = "geniza.wsgi.application"


# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "geniza",
        "USER": "geniza",
        "PASSWORD": "",
        "HOST": "",  # empty string for localhost
        "PORT": "",  # empty string for default
    }
}

SOLR_CONNECTIONS = {
    "default": {
        "URL": "http://localhost:8983/solr/",
        "COLLECTION": "geniza",
        "CONFIGSET": "geniza",
        "TEST": {
            # set aggressive commitWithin when testing
            "COMMITWITHIN": 750,
        },
    }
}


# Authentication backends
# https://docs.djangoproject.com/en/3.1/topics/auth/customizing/#specifying-authentication-backends

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "django_cas_ng.backends.CASBackend",
)


# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGE_CODE = "en"

TIME_ZONE = "America/New_York"

USE_I18N = True
WAGTAIL_I18N_ENABLED = True

USE_L10N = True

USE_TZ = True

WAGTAIL_CONTENT_LANGUAGES = LANGUAGES = [
    ("en", "English"),
    ("he", "Hebrew"),
    ("ar", "Arabic"),
]

LOCALE_PATHS = [BASE_DIR / "geniza" / "locale"]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/

STATIC_ROOT = BASE_DIR / "static"

STATIC_URL = "/static/"

STATICFILES_DIRS = [
    BASE_DIR / "sitemedia",
]

# Production webpack config: cache immediately upon loading the manifest
WEBPACK_LOADER = {
    "DEFAULT": {
        "CACHE": True,
        "BUNDLE_DIR_NAME": "sitemedia/bundles/",  # must end with slash
        "STATS_FILE": BASE_DIR / "sitemedia" / "webpack-stats.json",
        "POLL_INTERVAL": 0.1,
        "TIMEOUT": None,
        "IGNORE": [r".+\.hot-update.js", r".+\.map"],
    }
}

# pucas configuration that is not expected to change across deploys
# and does not reference local server configurations or fields
PUCAS_LDAP = {
    # basic user profile attributes
    "ATTRIBUTES": ["givenName", "sn", "mail"],
    "ATTRIBUTE_MAP": {
        "first_name": "givenName",
        "last_name": "sn",
        "email": "mail",
    },
}

# username for logging scripted activity
SCRIPT_USERNAME = "script"

# username for representing activity by entire team, or no specific user
TEAM_USERNAME = "pgl"

# use default Django site
SITE_ID = 1

# increase max from default 1000 to handle editing sources with lots of footnotes
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000

# configure default auto field for models
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# documentation links
PGP_DOCTYPE_GUIDE = "https://docs.google.com/document/d/1FHr1iS_JD5h-y5O1rv5JNNw1OqEVQFb-vSTGr3hoiF4/edit"

# django-csp configuration for content security policy definition and
# violation reporting - https://github.com/mozilla/django-csp
#
# uses lighthouse recommended strict CSP config with nonce for scripts. this
# is the "modern" CSP config that doesn't use a whitelist and is instead based
# on nonces generated on the server. For more info: https://web.dev/strict-csp
CSP_INCLUDE_NONCE_IN = ("script-src",)
CSP_SCRIPT_SRC = ["'strict-dynamic'", "https: 'unsafe-inline'"]
CSP_OBJECT_SRC = ("'none'",)
CSP_BASE_URI = ("'none'",)

# allow XMLHttpRequest or Fetch requests locally (for search), iiif manifests
CSP_CONNECT_SRC = [
    "'self'",
    "*.google-analytics.com",
    "*.lib.cam.ac.uk",
    "*.example.com",
    "iiif-cloud.princeton.edu",
]

# allow loading css locally & via inline styles
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")  # , 'unpkg.com')

# whitelisted image sources - analytics (tracking pixel?), IIIF, maps, etc.
CSP_IMG_SRC = (
    "'self'",
    "iiif.princeton.edu",
    "figgy.princeton.edu",
    "iiif-cloud.princeton.edu",
    "*.lib.cam.ac.uk",
    "data:",
)

# exclude admin and cms urls from csp directives since they're authenticated
CSP_EXCLUDE_URL_PREFIXES = ("/admin", "/cms")

# use jpg instead of png since some providers only support jpg
DJIFFY_THUMBNAIL_FORMAT = "jpg"
# disable djiffy import check, since we are not using djiffy views
# DJIFFY_IMPORT_CHECK_SUPPORTED = False

# URL for git repository of TEI transcriptions
TEI_TRANSCRIPTIONS_GITREPO = (
    "https://bitbucket.org/benjohnston/princeton-geniza-project.git"
)
# local path where git repo should be cloned
TEI_TRANSCRIPTIONS_LOCAL_PATH = "data/tei_xml"

# Media root for user uploads (required by wagtail)
MEDIA_ROOT = BASE_DIR / "media"

# Media URL for user uploads (required by wagtail)
MEDIA_URL = "/media/"

# Wagtail site name
WAGTAIL_SITE_NAME = "GENIZA"

# default font base url
FONT_URL_PREFIX = "/static/fonts/"

# Taggit customization
TAGGIT_TAGS_FROM_STRING = "geniza.common.utils.custom_tag_string"
# See issue #499
# TAGGIT_CASE_INSENSITIVE = True
