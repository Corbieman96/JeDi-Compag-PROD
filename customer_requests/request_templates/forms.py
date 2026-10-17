from django import forms

from customer_requests.request_templates.models import CustomerRequestTemplate
from customer_requests.request_templates.services.create_from_payload import (
    normalize_recurrence_weekdays,
)
from waste_docs.forms.customer_request import WEEKDAY_CHOICES


class CustomerRequestTemplateForm(forms.ModelForm):
    recurrence_weekdays_pick = forms.MultipleChoiceField(
        choices=WEEKDAY_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Dny v týdnu",
    )

    class Meta:
        model = CustomerRequestTemplate
        fields = (
            "title",
            "name",
            "waste_type",
            "suffix",
            "address",
            "fulfillment_latitude",
            "fulfillment_longitude",
            "activity",
            "vehicle_kind",
            "facility_address_snapshot",
            "contact_phone",
            "contact_note",
            "contract_number",
            "note",
            "is_recurring",
        )
        labels = {
            "title": "Název šablony",
            "name": "Název F/P osoby",
            "waste_type": "Druh odpadu",
            "suffix": "Koncovka",
            "address": "Adresa plnění",
            "fulfillment_latitude": "Zeměpisná šířka",
            "fulfillment_longitude": "Zeměpisná délka",
            "activity": "Činnost",
            "vehicle_kind": "Druh vozidla",
            "facility_address_snapshot": "Adresa provozovny",
            "contact_phone": "Telefon",
            "contact_note": "Poznámka ke kontaktu",
            "contract_number": "Číslo smlouvy",
            "note": "Poznámka požadavku",
            "is_recurring": "Pravidelný požadavek",
        }
        help_texts = {
            "is_recurring": "Datum požadavku a „Pravidelnost do“ se do šablony neukládají.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial["recurrence_weekdays_pick"] = [
                x
                for x in (self.instance.recurrence_weekdays or "").split(",")
                if x in {c[0] for c in WEEKDAY_CHOICES}
            ]

    def clean(self):
        cleaned = super().clean()
        is_recurring = cleaned.get("is_recurring")
        weekdays = normalize_recurrence_weekdays(cleaned.get("recurrence_weekdays_pick") or [])
        if is_recurring and not weekdays:
            self.add_error("recurrence_weekdays_pick", "U pravidelné šablony vyberte dny.")
        if not is_recurring:
            weekdays = ""
        cleaned["recurrence_weekdays"] = weekdays
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.recurrence_weekdays = self.cleaned_data.get("recurrence_weekdays") or ""
        if not instance.is_recurring:
            instance.recurrence_weekdays = ""
        if commit:
            instance.save()
        return instance
