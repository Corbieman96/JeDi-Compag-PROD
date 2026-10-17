from catalogs.models import NameSubjectProfile
from waste_docs.services.search_normalize import normalize_search_text

__all__ = ["normalize_search_text", "subject_search_blob"]


def subject_search_blob(item: NameSubjectProfile) -> str:
    return " ".join(
        [
            item.ico.value if item.ico_id else "",
            item.name.value if item.name_id else "",
            item.company_name or "",
        ]
    )
