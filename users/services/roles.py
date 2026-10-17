from django.contrib.auth.models import Group

from users.constants import ROLE_ADMIN, ROLE_CHOICES


def ensure_role_groups():
    for role_name, _ in ROLE_CHOICES:
        Group.objects.get_or_create(name=role_name)


def set_user_role(user, role_name: str):
    ensure_role_groups()
    user.groups.clear()
    role_group = Group.objects.get(name=role_name)
    user.groups.add(role_group)
    user.is_superuser = role_name == ROLE_ADMIN
    user.is_staff = role_name == ROLE_ADMIN
    user.save(update_fields=["is_superuser", "is_staff"])


def get_user_role_label(user) -> str:
    if user.is_superuser:
        return ROLE_ADMIN
    first_group = user.groups.order_by("name").first()
    return first_group.name if first_group else "-"
