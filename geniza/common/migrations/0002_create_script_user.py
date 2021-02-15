# Generated by Django 3.1.6 on 2021-02-04 21:17

from django.conf import settings
from django.db import migrations


def create_script_user(apps, schema_editor):
    # create a 'script' user so that scripted actions can be logged
    # via django log entry
    User = apps.get_model('auth', 'User')
    User.objects.get_or_create(username=settings.SCRIPT_USERNAME,
                               is_staff=False, is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0001_content_editor_group'),
    ]

    operations = [
        migrations.RunPython(create_script_user,
                             reverse_code=migrations.RunPython.noop),
    ]
