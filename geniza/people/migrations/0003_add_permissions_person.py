# Generated by Django 3.1.7 on 2021-04-01 15:33

from django.contrib.auth.management import create_permissions
from django.db import migrations

# Models:
#   person
# Permissions:
#   view_person
#   add_person
#   change_person
#   delete_person

CONTENT_EDITOR = 'Content Editor'
# new permissions for content editor
content_editor_perms = [
    'view_person', 'add_person', 'change_person',
]


CONTENT_ADMIN = 'Content Admin'
# additional new permissions for content admin
content_admin_perms = [
    'delete_person'
]

def create_content_editor_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    # make sure permissions are created before loading the fixture
    # which references them
    # (when running migrations all at once, permissions may not yet exist)
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    editor_group = Group.objects.get(name=CONTENT_EDITOR)
    permissions = []
    for codename in content_editor_perms:
        # using explicit get so that there will be an error if an
        # expected permission is not found
        permissions.append(Permission.objects.get(codename=codename))
    editor_group.permissions.add(*permissions)

    # update content admin group; add to content edit permissions
    admin_group = Group.objects.get(name=CONTENT_ADMIN)
    for codename in content_admin_perms:
        permissions.append(Permission.objects.get(codename=codename))
    admin_group.permissions.add(*permissions)


class Migration(migrations.Migration):

    dependencies = [
        ('footnotes', '0005_add_permissions_source_sourcetype_footnotes'),
        ('people', '0002_add_translation_and_sort_name'),
    ]

    operations = [
        migrations.RunPython(create_content_editor_groups,
                             reverse_code=migrations.RunPython.noop)
    ]
