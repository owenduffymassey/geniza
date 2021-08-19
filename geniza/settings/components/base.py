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
    "geniza.apps.GenizaAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.humanize",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
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
    "geniza.common",
    "geniza.corpus.apps.CorpusAppConfig",
    "geniza.footnotes.apps.FootnotesConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
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

LANGUAGE_CODE = "en-us"

TIME_ZONE = "America/New_York"

USE_I18N = True

USE_L10N = True

USE_TZ = True

LANGUAGES = [
    ("en", "English"),
    ("he", "Hebrew"),
    ("ar", "Arabic"),
]

LOCALE_PATHS = [BASE_DIR / "geniza" / "locale"]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/

STATIC_ROOT = BASE_DIR / "static"

STATIC_URL = "/static/"

# disable until this exists, since otherwise collectstatic fails
STATICFILES_DIRS = [
    BASE_DIR / "sitemedia",
]

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


# documentation links
PGP_DOCTYPE_GUIDE = "https://docs.google.com/document/d/1FHr1iS_JD5h-y5O1rv5JNNw1OqEVQFb-vSTGr3hoiF4/edit"
