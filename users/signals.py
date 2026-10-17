from django.db.models.signals import post_migrate
from django.dispatch import receiver

from users.services import ensure_role_groups


@receiver(post_migrate)
def create_default_roles(sender, **kwargs):
    if sender.name == "users":
        ensure_role_groups()
