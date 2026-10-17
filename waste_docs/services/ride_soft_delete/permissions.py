from users.services.access import can_see_all_waste_docs
from users.services.waste_doc_permissions import can_archive_pruvodka
from waste_docs.models import Pruvodka


def can_soft_delete_pruvodka(user, pruvodka: Pruvodka) -> bool:
    if not can_archive_pruvodka(user):
        return False
    if pruvodka.is_blank_pruvodka:
        return False
    if can_see_all_waste_docs(user):
        return True
    return pruvodka.created_by_id == user.id


def can_view_soft_delete_log(user) -> bool:
    return can_archive_pruvodka(user)
