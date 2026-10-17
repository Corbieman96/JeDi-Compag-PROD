from __future__ import annotations

import os
from django import forms
from django.core.exceptions import ValidationError

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    WasteTypeCatalog,
)
from catalogs.services.phone import format_czech_contact_phone
from catalogs.services.waste_type_lookup import resolve_waste_type_from_combo_text
from waste_docs.follow_up_options import (
    allowed_follow_up_activity_ids,
    has_follow_up_option,
    primary_follow_up_activity,
)
from catalogs.services.waste_type_labels import waste_type_combo_metadata
from customer_requests.models import CustomerRequest
from waste_docs.services.customer_request_date_closure import target_date_closure_error
from waste_docs.services.customer_request_follow_up import follow_up_target_date_error
from waste_docs.services.operating_calendar.resolve import apply_operating_date_shift

ALLOWED_ATTACHMENT_EXTS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"}
WEEKDAY_CHOICES = (
    ("0", "Po"),
    ("1", "Út"),
    ("2", "St"),
    ("3", "Čt"),
    ("4", "Pá"),
    ("5", "So"),
    ("6", "Ne"),
)


class CustomerRequestForm(forms.ModelForm):
    name_existing = forms.ModelChoiceField(
        queryset=NameCatalog.objects.order_by("value"),
        required=False,
        label="Název F/P osoby",
        widget=forms.HiddenInput(),
    )
    name_lookup = forms.CharField(required=False, max_length=255, label="Název F/P osoby")
    waste_type_lookup = forms.CharField(
        required=False,
        max_length=255,
        label="Druh odpadu (combobox)",
        widget=forms.HiddenInput(),
    )
    facility_address_value = forms.CharField(required=False, max_length=255, label="Adresa provozovny")
    contact_phone = forms.CharField(required=False, max_length=20, label="Telefon")
    contact_note = forms.CharField(
        required=False,
        max_length=200,
        label="Poznámka do jízdy",
        help_text="Tento text se propisuje do jízdy.",
    )
    address_value = forms.CharField(required=False, max_length=255, label="Adresa plnění")
    fulfillment_latitude = forms.DecimalField(required=False, max_digits=10, decimal_places=7, widget=forms.HiddenInput())
    fulfillment_longitude = forms.DecimalField(required=False, max_digits=10, decimal_places=7, widget=forms.HiddenInput())
    recurrence_weekdays_pick = forms.MultipleChoiceField(
        required=False,
        label="Dny v týdnu",
        choices=WEEKDAY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
    )
    attachment_1 = forms.FileField(required=False, label="Příloha 1")
    attachment_2 = forms.FileField(required=False, label="Příloha 2")
    attachment_3 = forms.FileField(required=False, label="Příloha 3")

    class Meta:
        model = CustomerRequest
        fields = [
            "name_existing",
            "activity",
            "vehicle_kind",
            "waste_type",
            "suffix",
            "target_date",
            "contract_number",
            "contact_phone",
            "contact_note",
            "note",
            "has_follow_up",
            "follow_up_activity",
            "follow_up_target_date",
            "is_recurring",
            "recurrence_until",
            "requires_advance_invoice",
            "advance_invoice_amount",
            "invoice_due_date",
        ]
        widgets = {
            "target_date": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 2}),
            "recurrence_until": forms.DateInput(attrs={"type": "date"}),
            "follow_up_target_date": forms.DateInput(attrs={"type": "date"}),
            "contact_note": forms.Textarea(attrs={"rows": 2}),
            "invoice_due_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "note": "Poznámka k požadavku",
        }
        help_texts = {
            "note": "Jen pro dispečera — do jízdy se nezaznamená.",
        }

    def __init__(self, *args, **kwargs):
        self.submit_user = kwargs.pop("submit_user", None)
        self.operating_date_shift_notes: list[str] = []
        super().__init__(*args, **kwargs)
        self.fields["activity"].queryset = ActivityCatalog.objects.filter(
            visible_for_submitter=True,
            require_nitropodnikovy_subjekt=False,
        ).order_by("name")
        self.fields["waste_type"].queryset = WasteTypeCatalog.objects.order_by("value")
        self.fields["vehicle_kind"].queryset = VehicleKindCatalog.objects.order_by("sort_order", "name")
        self.fields["vehicle_kind"].required = True
        self.fields["suffix"].queryset = SuffixCatalog.objects.order_by("value")
        self.fields["follow_up_activity"].queryset = ActivityCatalog.objects.order_by("name")

        if self.instance and self.instance.pk:
            self.fields["name_existing"].initial = self.instance.name_id
            self.fields["name_lookup"].initial = self.instance.name.value if self.instance.name_id else ""
            self.fields["address_value"].initial = self.instance.address.value if self.instance.address_id else ""
            self.fields["facility_address_value"].initial = self.instance.facility_address_snapshot or ""
            self.fields["contact_phone"].initial = self.instance.contact_phone or ""
            self.fields["contact_note"].initial = self.instance.contact_note or ""
            self.initial["fulfillment_latitude"] = self.instance.fulfillment_latitude
            self.initial["fulfillment_longitude"] = self.instance.fulfillment_longitude
            self.initial["recurrence_weekdays_pick"] = [
                x for x in (self.instance.recurrence_weekdays or "").split(",") if x in {c[0] for c in WEEKDAY_CHOICES}
            ]
            if self.instance.waste_type_id:
                meta = waste_type_combo_metadata()
                row = meta.get(str(self.instance.waste_type_id))
                if row:
                    self.fields["waste_type_lookup"].initial = row["label"]
            if not (self.instance.contract_number or "").strip():
                if self.instance.name_id and self.instance.waste_type_id:
                    pair = NameSubjectWasteSuffixPair.objects.filter(
                        subject_profile__name_id=self.instance.name_id,
                        waste_type_id=self.instance.waste_type_id,
                        suffix_id=self.instance.suffix_id,
                    ).first()
                    if pair and (pair.contract_number or "").strip():
                        self.initial["contract_number"] = pair.contract_number.strip()
        if not self.fields["name_lookup"].initial:
            self.fields["name_lookup"].initial = ""
        if not self.fields["address_value"].initial:
            self.fields["address_value"].initial = ""
        self.fields["contact_phone"].widget.attrs.update(
            {"placeholder": "000 000 000", "inputmode": "tel", "autocomplete": "tel"}
        )
        self.fields["facility_address_value"].help_text = "Formát: Ulice č.p. Město (automaticky se normalizuje)."
        self.fields["contact_phone"].help_text = "Ve tvaru 000 000 000"
        self.fields["contract_number"].help_text = "Číslo smlouvy (volitelné)."
        self.fields["follow_up_target_date"].help_text = (
            "Volitelné — doplníte později, pokud termín navazující činnosti ještě není znám."
        )
        self.fields["advance_invoice_amount"].required = False
        self.fields["waste_type"].required = False
        for field_name in ("name_existing", "waste_type", "waste_type_lookup"):
            self.fields[field_name].widget.is_required = False

        name_for_filter = None
        if self.instance and self.instance.pk and self.instance.name_id:
            name_for_filter = self.instance.name
        else:
            name_id = self.initial.get("name_existing") or (self.data.get("name_existing") if self.data else None)
            if name_id:
                name_for_filter = NameCatalog.objects.filter(pk=name_id).first()
        allowed_waste_ids = self._allowed_waste_type_ids_for_name(name_for_filter)
        if allowed_waste_ids:
            self.fields["waste_type"].queryset = WasteTypeCatalog.objects.filter(
                pk__in=allowed_waste_ids
            ).order_by("value")

    def _allowed_waste_type_ids_for_name(self, name_existing: NameCatalog | None) -> set[int] | None:
        if not name_existing:
            return None
        profile = (
            NameSubjectProfile.objects.prefetch_related(
                "waste_suffix_pairs",
                "allowed_waste_types",
            )
            .filter(name_id=name_existing.pk)
            .first()
        )
        if not profile:
            return None
        pair_waste_ids = {p.waste_type_id for p in profile.waste_suffix_pairs.all() if p.waste_type_id}
        allowed_ids = pair_waste_ids or set(profile.allowed_waste_types.values_list("id", flat=True))
        return allowed_ids or None

    def _resolve_waste_type_from_lookup(
        self,
        label: str,
        *,
        allowed_ids: set[int] | None = None,
    ) -> WasteTypeCatalog | None:
        return resolve_waste_type_from_combo_text(label, allowed_ids=allowed_ids)

    def clean(self):
        cleaned = super().clean()
        name_existing = cleaned.get("name_existing")
        name_lookup = (cleaned.get("name_lookup") or "").strip()
        if not name_existing and name_lookup:
            name_existing = NameCatalog.objects.filter(value=name_lookup).first()
            cleaned["name_existing"] = name_existing
        if not name_existing:
            raise ValidationError("Vyberte Název F/P osoby z comboboxu, nebo založte novou osobu tlačítkem.")

        activity = cleaned.get("activity")
        if activity and (not activity.visible_for_submitter or activity.require_nitropodnikovy_subjekt):
            self.add_error("activity", "Tuto činnost nelze použít v zákaznickém požadavku.")

        has_follow_up = cleaned.get("has_follow_up")
        follow_up_activity = cleaned.get("follow_up_activity")
        follow_up_target_date = cleaned.get("follow_up_target_date")
        target_date = cleaned.get("target_date")
        if target_date:
            target_date, shift_note = apply_operating_date_shift(
                target_date, user=self.submit_user
            )
            cleaned["target_date"] = target_date
            if shift_note:
                self.operating_date_shift_notes.append(shift_note)
            unchanged_date = (
                self.instance
                and self.instance.pk
                and self.instance.target_date == target_date
            )
            if not unchanged_date:
                err = target_date_closure_error(target_date, user=self.submit_user)
                if err:
                    self.add_error("target_date", err)
        allowed_follow_ids = set(allowed_follow_up_activity_ids(activity))
        activity_follow_up = primary_follow_up_activity(activity)
        if allowed_follow_ids:
            # Pokud má činnost pevně nastavenou návaznost, musí být aktivní vždy.
            cleaned["has_follow_up"] = True
            has_follow_up = True
        if has_follow_up and follow_up_activity and allowed_follow_ids and follow_up_activity.pk not in allowed_follow_ids:
            self.add_error(
                "follow_up_activity",
                "Vybraná navazující činnost neodpovídá nastavení u zvolené činnosti.",
            )
        if has_follow_up and not follow_up_activity and activity_follow_up:
            cleaned["follow_up_activity"] = activity_follow_up
        elif has_follow_up and not follow_up_activity:
            self.add_error("follow_up_activity", "Vyplňte navazující činnost.")
        if has_follow_up and follow_up_target_date:
            follow_up_target_date, follow_shift = apply_operating_date_shift(
                follow_up_target_date, user=self.submit_user
            )
            cleaned["follow_up_target_date"] = follow_up_target_date
            if follow_shift:
                self.operating_date_shift_notes.append(follow_shift)
        if has_follow_up and follow_up_target_date and target_date:
            err = follow_up_target_date_error(target_date, follow_up_target_date)
            if err:
                self.add_error("follow_up_target_date", err)
        if not has_follow_up:
            cleaned["follow_up_activity"] = None
            cleaned["follow_up_target_date"] = None

        address_value = (cleaned.get("address_value") or "").strip()
        if not address_value:
            self.add_error("address_value", "Vyplňte adresu plnění.")
        cleaned["address_value"] = address_value
        cleaned["facility_address_value"] = (cleaned.get("facility_address_value") or "").strip()
        cleaned["contact_note"] = (cleaned.get("contact_note") or "").strip()[:200]

        waste_type = cleaned.get("waste_type")
        allowed_waste_ids = self._allowed_waste_type_ids_for_name(name_existing)
        if not waste_type:
            lookup_label = (cleaned.get("waste_type_lookup") or "").strip()
            waste_type = self._resolve_waste_type_from_lookup(
                lookup_label,
                allowed_ids=allowed_waste_ids,
            )
            if waste_type:
                cleaned["waste_type"] = waste_type
        if not waste_type:
            self.add_error(
                "waste_type",
                "Vyberte druh odpadu z nabídky nebo zadejte platný kód (např. 20 01 40).",
            )

        vehicle_kind = cleaned.get("vehicle_kind")

        if name_existing and waste_type:
            profile = (
                NameSubjectProfile.objects.prefetch_related(
                    "waste_suffix_pairs__waste_type",
                    "waste_suffix_pairs__yard_vehicle_kind",
                    "allowed_waste_types",
                )
                .filter(name_id=name_existing.pk)
                .first()
            )
            if profile:
                pair_waste_ids = {p.waste_type_id for p in profile.waste_suffix_pairs.all() if p.waste_type_id}
                allowed_ids = pair_waste_ids or set(profile.allowed_waste_types.values_list("id", flat=True))
                if allowed_ids and waste_type.pk not in allowed_ids:
                    self.add_error(
                        "waste_type",
                        "Tento druh odpadu není u vybraného subjektu evidovaný v číselníku.",
                    )
                pair_rows = [
                    p
                    for p in profile.waste_suffix_pairs.prefetch_related("yard_vehicle_kinds").all()
                    if p.waste_type_id == waste_type.pk
                ]
                allowed_vehicle_kind_ids: set[int] = set()
                for p in pair_rows:
                    allowed_vehicle_kind_ids.update(
                        p.yard_vehicle_kinds.values_list("pk", flat=True)
                    )
                    if p.yard_vehicle_kind_id:
                        allowed_vehicle_kind_ids.add(p.yard_vehicle_kind_id)
                if pair_rows and not allowed_vehicle_kind_ids:
                    self.add_error(
                        "vehicle_kind",
                        "U tohoto odpadu není u subjektu nastaven druh vozidla. "
                        "Doplňte jej v sekci „Povolené odpady a koncovky“ u subjektu "
                        "(pole „Druhy vozidla (svoz)“).",
                    )
                elif allowed_vehicle_kind_ids:
                    if not vehicle_kind:
                        self.add_error(
                            "vehicle_kind",
                            "Pro vybraný druh odpadu vyberte druh vozidla (svoz).",
                        )
                    elif vehicle_kind.pk not in allowed_vehicle_kind_ids:
                        self.add_error(
                            "vehicle_kind",
                            "Vybraný druh vozidla neodpovídá párování odpadu u subjektu.",
                        )

        is_recurring = cleaned.get("is_recurring")
        weekdays_pick = cleaned.get("recurrence_weekdays_pick") or []
        weekdays = ",".join(weekdays_pick)
        has_forced_follow = has_follow_up_option(activity)
        if (has_follow_up or has_forced_follow) and is_recurring:
            self.add_error(
                "is_recurring",
                "Požadavek s navazující činností nelze plánovat pravidelně. Použijte jednorázové termíny.",
            )
        if is_recurring and not weekdays:
            self.add_error("recurrence_weekdays_pick", "U pravidelného požadavku vyberte dny.")
        if not is_recurring:
            cleaned["recurrence_weekdays"] = ""
            cleaned["recurrence_until"] = None
            cleaned["recurrence_weekdays_pick"] = []
        else:
            cleaned["recurrence_weekdays"] = weekdays

        requires_invoice = cleaned.get("requires_advance_invoice")
        amount = cleaned.get("advance_invoice_amount")
        due_date = cleaned.get("invoice_due_date")
        if requires_invoice and not amount:
            self.add_error("advance_invoice_amount", "Při záloze vyplňte částku.")
        if requires_invoice and not due_date:
            self.add_error("invoice_due_date", "Při záloze vyplňte den splatnosti.")
        if requires_invoice and due_date and target_date and due_date < target_date:
            self.add_error(
                "invoice_due_date",
                "Splatnost zálohy musí být stejná nebo pozdější než datum požadavku.",
            )
        if not requires_invoice:
            cleaned["advance_invoice_amount"] = None
            cleaned["invoice_due_date"] = None

        if target_date and not self.errors.get("target_date"):
            from waste_docs.customer_request_kind_closure.services.checks import (
                vehicle_kind_closure_error,
            )

            vk = cleaned.get("vehicle_kind")
            vk_id = vk.pk if vk else None
            if not vk_id and activity:
                kinds = list(activity.vehicle_kinds.order_by("sort_order", "name", "pk")[:2])
                if len(kinds) == 1:
                    vk_id = kinds[0].pk
            unchanged_kind = (
                self.instance
                and self.instance.pk
                and self.instance.target_date == target_date
                and (self.instance.vehicle_kind_id or None) == (vk_id or None)
            )
            if not unchanged_kind:
                err = vehicle_kind_closure_error(
                    target_date, vk_id, user=self.submit_user
                )
                if err:
                    self.add_error("target_date", err)

        return cleaned

    def clean_address_value(self):
        return (self.cleaned_data.get("address_value") or "").strip()

    def clean_contact_phone(self):
        raw = (self.cleaned_data.get("contact_phone") or "").strip()
        if not raw:
            return ""
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) < 9:
            raise ValidationError("Telefon musí mít alespoň 9 číslic (např. 000 000 000).")
        return format_czech_contact_phone(raw)

    def clean_attachment_1(self):
        return self._clean_attachment_field("attachment_1")

    def clean_attachment_2(self):
        return self._clean_attachment_field("attachment_2")

    def clean_attachment_3(self):
        return self._clean_attachment_field("attachment_3")

    def _clean_attachment_field(self, field_name: str):
        f = self.cleaned_data.get(field_name)
        if not f:
            return f
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in ALLOWED_ATTACHMENT_EXTS:
            raise ValidationError("Povolené přílohy: PDF, JPG, PNG, DOC, DOCX.")
        return f
