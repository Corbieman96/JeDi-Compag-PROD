from datetime import timedelta

from waste_docs.models import Pruvodka


def build_pruvodka_copy_payload(source: Pruvodka) -> dict:
    return {
        "activity_id": source.activity_id,
        "name_id": source.name_id,
        "ico_id": source.ico_id,
        "address_id": source.address_id,
        "waste_type_id": source.waste_type_id,
        "waste_code_id": source.waste_code_id,
        "waste_category_id": source.waste_category_id,
        "vehicle_rz_id": source.vehicle_rz_id,
        "driver_id": source.driver_id,
        "suffix_id": source.suffix_id,
        "drive_date": source.drive_date,
        "container_number": source.container_number,
        "container_number_2": source.container_number_2,
        "container_passport_id": source.container_passport_id,
        "contact_phone": source.contact_phone,
        "contract_number": source.contract_number,
        "contact_note": source.contact_note,
    }


def batch_peers_for_generated_copies(item: Pruvodka):
    """Find rides likely created in one repeat_count submit."""
    if not item.created_at:
        return Pruvodka.objects.filter(pk=item.pk, is_archived=False)
    window_start = item.created_at - timedelta(seconds=15)
    window_end = item.created_at + timedelta(seconds=15)
    return (
        Pruvodka.objects.filter(
            created_by_id=item.created_by_id,
            is_archived=False,
            created_at__gte=window_start,
            created_at__lte=window_end,
            drive_date=item.drive_date,
            activity_id=item.activity_id,
            name_id=item.name_id,
            ico_id=item.ico_id,
            address_id=item.address_id,
            waste_type_id=item.waste_type_id,
            waste_code_id=item.waste_code_id,
            waste_category_id=item.waste_category_id,
            vehicle_rz_id=item.vehicle_rz_id,
            driver_id=item.driver_id,
            suffix_id=item.suffix_id,
            container_number=item.container_number,
            container_number_2=item.container_number_2,
            container_passport_id=item.container_passport_id,
            contact_phone=item.contact_phone,
            contract_number=item.contract_number,
            contact_note=item.contact_note,
        )
        .select_related("activity")
        .order_by("pk")
    )
