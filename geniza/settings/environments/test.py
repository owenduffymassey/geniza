import os

from geniza.settings.components.base import DATABASES

# These settings correspond to the service container settings in the
# .github/workflow .yml files.
DATABASES['default'].update({
    'ENGINE': 'django.db.backends.%s' % os.getenv('DJANGO_DB_BACKEND'),
    'PASSWORD': os.getenv('DB_PASSWORD'),
    'USER': os.getenv('DB_USER'),
    'NAME': os.getenv('DB_NAME'),
})

# turn off debug so we see 404s when testing
DEBUG = False

# required for tests when DEBUG = False
ALLOWED_HOSTS = ['*']
