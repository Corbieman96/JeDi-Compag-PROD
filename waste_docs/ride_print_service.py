from catalogs.models import NameSubjectWasteSuffixPair

from pio.services import effective_pio_file
from waste_docs.zpo_resolved import effective_zpo_file, pair_for_name_waste_suffix, zpo_kind_for_file


def build_ride_print_rows(rides):
    """Build printable ride rows with linked ZPO/PIO documents."""
    rides = list(rides)
    if not rides:
        return []

    output = []
    for ride in rides:
        pair = None
        if ride.name_id and ride.waste_type_id and ride.suffix_id:
            pair = pair_for_name_waste_suffix(ride.name_id, ride.waste_type_id, ride.suffix_id)
        zpo_f = effective_zpo_file(pair)
        pio_f = effective_pio_file(pair)
        output.append(
            {
                "ride": ride,
                "pair_docs": pair,
                "zpo_kind": zpo_kind_for_file(zpo_f),
                "pio_kind": _doc_kind(pio_f.name if pio_f else ""),
            }
        )
    return output


def _doc_kind(name: str) -> str:
    lower = (name or "").lower()
    if lower.endswith(".pdf"):
        return "pdf"
    if lower.endswith(".png") or lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image"
    return "other"

