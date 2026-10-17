"""Uložení CustomerRequestForm do modelu (create i oprava)."""

from __future__ import annotations

from catalogs.models import AddressCatalog
from customer_requests.models import CustomerRequest, CustomerRequestAttachment
from waste_docs.forms.customer_request import CustomerRequestForm


def save_attachments_from_form(form: CustomerRequestForm, item: CustomerRequest) -> None:
    for idx in (1, 2, 3):
        uploaded = form.cleaned_data.get(f"attachment_{idx}")
        if not uploaded:
            continue
        CustomerRequestAttachment.objects.filter(request=item, sort_order=idx).delete()
        CustomerRequestAttachment.objects.create(request=item, sort_order=idx, file=uploaded)


def apply_form_to_request(*, form: CustomerRequestForm, item: CustomerRequest) -> CustomerRequest:
    name_obj = form.cleaned_data["name_existing"]
    address_value = form.cleaned_data["address_value"]
    address_obj, _ = AddressCatalog.objects.get_or_create(value=address_value)

    draft = form.save(commit=False)
    for field in CustomerRequestForm.Meta.fields:
        if field == "name_existing":
            continue
        setattr(item, field, getattr(draft, field))

    item.name = name_obj
    item.address = address_obj
    item.fulfillment_latitude = form.cleaned_data.get("fulfillment_latitude")
    item.fulfillment_longitude = form.cleaned_data.get("fulfillment_longitude")
    item.facility_address_snapshot = (form.cleaned_data.get("facility_address_value") or "").strip()
    item.recurrence_weekdays = form.cleaned_data.get("recurrence_weekdays") or ""
    item.save()
    save_attachments_from_form(form, item)
    return item
