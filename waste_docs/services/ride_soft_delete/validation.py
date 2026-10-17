from waste_docs.services.ride_soft_delete.errors import RideSoftDeleteError

MIN_REASON_LEN = 5
MAX_REASON_LEN = 500


def validate_soft_delete_reason(reason: str) -> str:
    cleaned = (reason or "").strip()
    if len(cleaned) < MIN_REASON_LEN:
        raise RideSoftDeleteError(
            f"Důvod smazání musí mít alespoň {MIN_REASON_LEN} znaků."
        )
    if len(cleaned) > MAX_REASON_LEN:
        raise RideSoftDeleteError(
            f"Důvod smazání může mít nejvýše {MAX_REASON_LEN} znaků."
        )
    return cleaned
