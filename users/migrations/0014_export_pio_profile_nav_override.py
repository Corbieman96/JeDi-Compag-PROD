# Generated manually

from django.db import migrations, models

ALLOWED_ROLES = {"Admin", "Dispečer", "Zadavatel"}


def migrate_pio_export_permission(apps, schema_editor):
    UserAccessProfile = apps.get_model("users", "UserAccessProfile")
    User = apps.get_model("auth", "User")
    Group = apps.get_model("auth", "Group")

    role_by_user_id: dict[int, str] = {}
    for user in User.objects.filter(is_superuser=True).only("id"):
        role_by_user_id[user.id] = "Admin"
    for group in Group.objects.filter(name__in=ALLOWED_ROLES).prefetch_related("user_set"):
        for user in group.user_set.all():
            if user.id not in role_by_user_id:
                role_by_user_id[user.id] = group.name

    for prof in UserAccessProfile.objects.all().iterator():
        old_allowed = bool(getattr(prof, "can_export_name_subject_pio_profile", True))
        role = role_by_user_id.get(prof.user_id, "")
        if old_allowed:
            prof.export_pio_profile = "inherit"
        elif role in ALLOWED_ROLES:
            prof.export_pio_profile = "inherit"
        else:
            prof.export_pio_profile = "hide"
        prof.save(update_fields=["export_pio_profile"])


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0013_useraccessprofile_can_create_pruvodka"),
    ]

    operations = [
        migrations.AddField(
            model_name="useraccessprofile",
            name="export_pio_profile",
            field=models.CharField(
                choices=[("inherit", "Dědit z role"), ("show", "Vždy zobrazit"), ("hide", "Skrýt")],
                default="inherit",
                help_text="Tlačítko Vygenerovat PIO na úpravě subjektu v číselníku jmen. "
                "Superuser má vždy přístup; ostatní dědí z Nastavení podle role, pokud je zde „Dědit z role“.",
                max_length=16,
                verbose_name="PIO — profilová šablona u subjektu F/P",
            ),
        ),
        migrations.RunPython(migrate_pio_export_permission, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="useraccessprofile",
            name="can_export_name_subject_pio_profile",
        ),
    ]
