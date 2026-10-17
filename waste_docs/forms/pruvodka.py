import os

from django import forms
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from catalogs.models import (
    ActivityCatalog,
    ActivityFieldKey,
    ActivityFieldMode,
    AddressCatalog,
    ContainerPassport,
    DriverProfile,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    VehicleKindCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from catalogs.services.phone import format_czech_contact_phone
from catalogs.services.fulfillment_address import (
    is_valid_fulfillment_address_strict,
    normalize_fulfillment_address,
)
from catalogs.waste_catalog_code import normalize_waste_catalog_code
from users.services.sberny_dvur import get_sberny_dvur_subject, is_sberny_dvur_role
from users.services.access import can_see_all_waste_docs
from waste_docs.activity_fields import get_effective_mode
from waste_docs.follow_up_options import allowed_follow_up_activity_ids
from waste_docs.follow_up_prefill import _fulfillment_value_for_item
from waste_docs.services.follow_up_chain import parent_has_terminal_child, has_follow_up_option
from waste_docs.forms.customer_request import ALLOWED_ATTACHMENT_EXTS
from waste_docs.services.container_passport_ride_validation import iter_container_passport_validation_errors
from catalogs.models.vehicle_rz import VehicleRzCatalog
from waste_docs.services.follow_up_pair_context import (
    follow_up_inherits_parent_pair,
    preferred_pair_id_for_follow_up,
)
from waste_docs.services.follow_up_vehicle_kind import (
    allowed_follow_kind_ids_for_parent_rz,
    follow_up_vehicle_kind_error,
)
from waste_docs.services.yard_form_activity import yard_standalone_activity_id_from_form_data
from waste_docs.yard_matrix import pruvodka_new_date_pairs_qs, yard_new_date_matrix_ready_qs

from waste_docs.models import Pruvodka, SvozTask


def _form_checkbox_truthy(raw) -> bool:
    if raw is True:
        return True
    if raw is None:
        return False
    return str(raw).strip().lower() in {"1", "true", "on", "yes"}
from waste_docs.services.pruvodka_attachments import (
    MAX_PRUVODKA_ATTACHMENTS,
    remaining_attachment_slots,
)


class PruvodkaForm(forms.ModelForm):
    # Skryté selecty (řidič, RZ, odpad) mají viditelné comboboxy — nativní HTML5 validace by blokovala odeslání.
    use_required_attribute = False

    drive_date = forms.DateField(
        required=True,
        label="Datum jízdy",
        input_formats=["%Y-%m-%d", "%d.%m.%Y"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    ico_lookup = forms.CharField(
        required=False,
        label="Vyhledat subjekt",
        widget=forms.TextInput(attrs={"placeholder": "Název firmy/F osoby (našeptávač z číselníku)"}),
    )
    waste_code_display = forms.CharField(
        required=False,
        label="Katalogové číslo odpadu",
        widget=forms.TextInput(attrs={"readonly": "readonly"}),
    )
    waste_category_display = forms.CharField(
        required=False,
        label="Kategorie odpadu",
        widget=forms.TextInput(attrs={"readonly": "readonly"}),
    )
    facility_address_display = forms.CharField(
        required=False,
        label="Adresa provozovny",
        widget=forms.TextInput(attrs={"readonly": "readonly"}),
    )
    container_number = forms.CharField(
        required=False,
        label="Číslo kontejneru (1)",
        max_length=50,
    )
    container_number_2 = forms.CharField(
        required=False,
        label="Číslo kontejneru (2) — druhý při výměně",
        max_length=50,
    )
    contact_phone = forms.CharField(
        required=False,
        label="Telefon",
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "placeholder": "000 000 000",
                "inputmode": "tel",
                "autocomplete": "tel",
            }
        ),
    )
    contract_number = forms.CharField(
        required=False,
        label="Číslo smlouvy",
        max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Číslo smlouvy"}),
    )
    contact_note = forms.CharField(
        required=False,
        label="Poznámka",
        max_length=200,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    fulfillment_address_value = forms.CharField(
        required=True,
        label="Adresa plnění",
        widget=forms.TextInput(attrs={"placeholder": "Zadejte adresu plnění"}),
    )
    skip_follow_up = forms.BooleanField(
        required=False,
        label="Nehlídat navazující jízdu",
        help_text="Zaškrtněte, pokud u této činnosti nechcete zařadit záznam mezi čekající návaznosti.",
    )
    follow_up_vehicle_rz_manual = forms.BooleanField(
        required=False,
        label="Ruční změna RZ vozidla",
        help_text=(
            "Zaškrtněte, pokud 1. část jela jiným druhem než skutečně potřebná navazující jízda "
            "(např. přistaveno 3H, ale má jet H). Bez zaškrtnutí platí pravidlo silnějšího vozidla."
        ),
    )
    follow_up_parent = forms.ModelChoiceField(
        queryset=Pruvodka.objects.none(),
        required=False,
        widget=forms.HiddenInput(),
    )
    repeat_count = forms.IntegerField(
        required=True,
        label="Počet jízd",
        min_value=1,
        max_value=50,
        initial=1,
        widget=forms.NumberInput(attrs={"min": 1, "max": 50, "step": 1}),
    )

    class Meta:
        model = Pruvodka
        fields = (
            "activity",
            "drive_date",
            "vehicle_rz",
            "container_passport",
            "driver",
            "waste_type",
            "name",
            "ico",
            "suffix",
            "container_number",
            "container_number_2",
            "contact_phone",
            "contract_number",
            "contact_note",
            "follow_up_parent",
        )
        labels = {
            "activity": "Činnost",
            "drive_date": "Datum jízdy",
            "vehicle_rz": "RZ vozidla",
            "container_passport": "Pasport kontejneru",
            "driver": "Řidič",
            "waste_type": "Název druhu odpadu",
            "name": "Název F/P osoby",
            "ico": "IČO",
            "suffix": "Koncovka",
            "container_number": "Číslo kontejneru (1)",
            "container_number_2": "Číslo kontejneru (2) — druhý při výměně",
            "contact_phone": "Telefon",
            "contract_number": "Číslo smlouvy",
            "contact_note": "Poznámka",
        }
        widgets = {}

    def __init__(self, *args, is_edit=False, user=None, yard_standalone_mode=False, **kwargs):
        self._is_edit = bool(is_edit)
        self._request_user = user
        self._yard_standalone_mode = bool(yard_standalone_mode)
        self._yard_drive_date_locked = bool(yard_standalone_mode)
        self.attachment_upload_slots: list[int] = []
        super().__init__(*args, **kwargs)
        activity_id = (self.data.get("activity") or "").strip() if hasattr(self, "data") and self.data else ""
        if not activity_id and self.initial.get("activity"):
            activity_id = str(self.initial.get("activity"))
        if not activity_id and self.instance and self.instance.activity_id:
            activity_id = str(self.instance.activity_id)

        if self._yard_standalone_mode and self._request_user and hasattr(self, "data") and self.data:
            resolved = yard_standalone_activity_id_from_form_data(self._request_user, self.data)
            if resolved:
                activity_id = resolved
        follow_parent_pk = None
        if self.initial.get("follow_up_parent") is not None:
            try:
                follow_parent_pk = int(self.initial.get("follow_up_parent"))
            except (TypeError, ValueError):
                follow_parent_pk = None
        if hasattr(self, "data") and self.data and (self.data.get("follow_up_parent") or "").strip():
            try:
                follow_parent_pk = int(self.data.get("follow_up_parent"))
            except ValueError:
                follow_parent_pk = None

        manual_vehicle_rz = False
        if hasattr(self, "data") and self.data:
            manual_vehicle_rz = _form_checkbox_truthy(self.data.get("follow_up_vehicle_rz_manual"))

        if follow_parent_pk:
            parent_for_activity_limit = (
                Pruvodka.objects.filter(pk=follow_parent_pk, is_archived=False)
                .select_related("activity", "vehicle_rz")
                .prefetch_related("activity__follow_up_activities", "vehicle_rz__profile__vehicle_kinds")
                .first()
            )
            allowed_activity_ids = allowed_follow_up_activity_ids(
                parent_for_activity_limit.activity if parent_for_activity_limit else None
            )
            if allowed_activity_ids:
                selected_activity_id = None
                if activity_id and str(activity_id).isdigit():
                    selected_activity_id = int(activity_id)
                if selected_activity_id and selected_activity_id not in allowed_activity_ids:
                    allowed_activity_ids = [*allowed_activity_ids, selected_activity_id]
                self.fields["activity"].queryset = ActivityCatalog.objects.filter(
                    pk__in=allowed_activity_ids
                ).order_by("name")
                self.fields["activity"].help_text = (
                    "Navazující druh činnosti zvolte v tomto poli — položky odpovídají číselníku činností, "
                    "nabídka je omezena na přípustné návaznosti z 1. části."
                )
            if parent_for_activity_limit and parent_for_activity_limit.vehicle_rz_id and not manual_vehicle_rz:
                allowed_kind_ids = allowed_follow_kind_ids_for_parent_rz(parent_for_activity_limit.vehicle_rz)
                if allowed_kind_ids:
                    parent_rz_pk = parent_for_activity_limit.vehicle_rz_id
                    filtered_rz_qs = (
                        self.fields["vehicle_rz"]
                        .queryset.filter(profile__vehicle_kinds__pk__in=allowed_kind_ids)
                        .distinct()
                    )
                    rz_pks = set(filtered_rz_qs.values_list("pk", flat=True))
                    rz_pks.add(parent_rz_pk)
                    self.fields["vehicle_rz"].queryset = VehicleRzCatalog.objects.filter(pk__in=rz_pks)
                    parent_rz = (parent_for_activity_limit.vehicle_rz_snapshot or "").strip()
                    self.fields["vehicle_rz"].help_text = (
                        "U navazující jízdy musí být stejný nebo silnější druh vozidla jako u 1. části "
                        "(3H může stáhnout H, ne naopak). U kombinace druhů na RZ 1. části stačí jeden z nich."
                        f"{f' — RZ {parent_rz}' if parent_rz else ''}."
                    )
            elif parent_for_activity_limit and parent_for_activity_limit.vehicle_rz_id and manual_vehicle_rz:
                parent_rz = (parent_for_activity_limit.vehicle_rz_snapshot or "").strip()
                self.fields["vehicle_rz"].help_text = (
                    "Ruční změna RZ — vyberte skutečné vozidlo pro navazující jízdu "
                    f"{f'(1. část: RZ {parent_rz})' if parent_rz else ''}."
                )

        self.fields["vehicle_rz"].queryset = self.fields["vehicle_rz"].queryset.select_related("profile")
        self.fields["vehicle_rz"].empty_label = "-----"
        self.fields["driver"].queryset = DriverProfile.objects.order_by("last_name", "first_name", "personal_number")
        self.fields["driver"].empty_label = "-----"
        follow_qs = Pruvodka.objects.none()
        successor_ids: list[int] = []
        if activity_id:
            try:
                act = (
                    ActivityCatalog.objects.filter(pk=int(activity_id))
                    .select_related("follow_up_activity")
                    .prefetch_related("follow_up_activities")
                    .first()
                )
                successor_ids = allowed_follow_up_activity_ids(act)
            except ValueError:
                successor_ids = []
        if successor_ids:
            base_follow_qs = Pruvodka.objects.filter(activity_id__in=successor_ids, is_archived=False)
            name_filter_id = None
            if hasattr(self, "data") and self.data and (self.data.get("name") or "").strip().isdigit():
                name_filter_id = int((self.data.get("name") or "").strip())
            elif self.initial.get("name"):
                try:
                    name_filter_id = int(self.initial.get("name"))
                except (TypeError, ValueError):
                    name_filter_id = None
            elif self.instance and self.instance.name_id:
                name_filter_id = self.instance.name_id
            if name_filter_id:
                base_follow_qs = base_follow_qs.filter(name_id=name_filter_id)
            if self._is_edit:
                follow_qs = base_follow_qs.filter(follow_up_children__isnull=True).select_related("activity")
            else:
                follow_qs = base_follow_qs.filter(follow_up_open=True).select_related("activity")
        if follow_parent_pk:
            follow_qs = (follow_qs | Pruvodka.objects.filter(pk=follow_parent_pk, is_archived=False)).distinct()
        self.fields["follow_up_parent"].queryset = follow_qs

        def _driver_label(obj):
            full_name = " ".join(part for part in [obj.last_name, obj.first_name] if part).strip() or obj.personal_number
            personal_number = (obj.personal_number or "").strip()
            if personal_number and personal_number not in full_name:
                return f"{full_name} ({personal_number})"
            return full_name

        self.fields["driver"].label_from_instance = _driver_label
        self.fields["ico"].widget = forms.HiddenInput()
        self.fields["name"].widget = forms.HiddenInput()
        self.fields["ico"].required = False
        self.fields["name"].required = False
        if self._is_edit:
            self.fields["repeat_count"].required = False
            self.fields["repeat_count"].initial = 1

        if self._yard_standalone_mode and self._request_user and is_sberny_dvur_role(self._request_user):
            ys = get_sberny_dvur_subject(self._request_user)
            if ys:
                wt_ids = yard_new_date_matrix_ready_qs(ys).values_list("waste_type_id", flat=True).distinct()
                self.fields["waste_type"].queryset = WasteTypeCatalog.objects.filter(pk__in=wt_ids).order_by(
                    "code", "value"
                )
            self.fields["activity"].required = False
            self.fields["activity"].widget = forms.HiddenInput()
            self.fields["drive_date"].widget.attrs["readonly"] = "readonly"

        mid_vehicle_container = ["driver", "vehicle_rz", "follow_up_vehicle_rz_manual"]
        if self._is_edit:
            mid_vehicle_container.append("container_passport")
        mid_vehicle_container.extend(
            ["container_number", "container_number_2", "contact_note"]
        )
        default_field_order = [
            "activity",
            "drive_date",
            "repeat_count",
            *mid_vehicle_container,
            "ico_lookup",
            "ico",
            "name",
            "fulfillment_address_value",
            "facility_address_display",
            "contact_phone",
            "contract_number",
            "waste_type",
            "waste_code_display",
            "waste_category_display",
            "suffix",
            "skip_follow_up",
            "follow_up_parent",
        ]
        yard_mid = ["driver", "vehicle_rz"]
        if self._is_edit:
            yard_mid.append("container_passport")
        yard_mid.extend(
            ["container_number", "container_number_2", "contact_note"]
        )
        yard_field_order = [
            "activity",
            "drive_date",
            "repeat_count",
            "waste_type",
            "waste_code_display",
            "waste_category_display",
            "suffix",
            *yard_mid,
            "ico_lookup",
            "ico",
            "name",
            "fulfillment_address_value",
            "facility_address_display",
            "contact_phone",
            "contract_number",
            "skip_follow_up",
            "follow_up_parent",
        ]
        if self._yard_standalone_mode:
            self.order_fields(yard_field_order)
        else:
            self.order_fields(default_field_order)

        if not self._is_edit:
            self.fields.pop("container_passport", None)

        if activity_id:
            try:
                activity_id_int = int(activity_id)
            except ValueError:
                activity_id_int = None
            if activity_id_int:
                rz_qs = self.fields["vehicle_rz"].queryset.filter(
                    profile__vehicle_kinds__activities__id=activity_id_int
                )
                if self._yard_standalone_mode and self._request_user and is_sberny_dvur_role(self._request_user):
                    ys = get_sberny_dvur_subject(self._request_user)
                    if ys and hasattr(self, "data") and self.data:
                        wt_raw = (self.data.get("waste_type") or "").strip()
                        suf_raw = (self.data.get("suffix") or "").strip()
                        if wt_raw.isdigit() and suf_raw.isdigit():
                            pair = yard_new_date_matrix_ready_qs(ys).filter(
                                waste_type_id=int(wt_raw),
                                suffix_id=int(suf_raw),
                            ).first()
                            if pair:
                                from catalogs.services.name_subject_pair_vehicle_kinds import (
                                    pair_covering_vehicle_kind_ids,
                                )

                                kind_ids = pair_covering_vehicle_kind_ids(pair)
                                if kind_ids:
                                    rz_qs = rz_qs.filter(profile__vehicle_kinds__pk__in=kind_ids)
                self.fields["vehicle_rz"].queryset = rz_qs.distinct()
                if self._is_edit:
                    rz_pk_list = list(self.fields["vehicle_rz"].queryset.values_list("pk", flat=True))
                    passport_qs = ContainerPassport.objects.none()
                    if rz_pk_list:
                        passport_qs = (
                            ContainerPassport.objects.filter(
                                vehicle_kind_id__in=VehicleKindCatalog.objects.filter(
                                    vehicle_profiles__rz_id__in=rz_pk_list
                                ).values_list("pk", flat=True)
                            )
                            .distinct()
                            .select_related("vehicle_kind")
                            .order_by(
                                "vehicle_kind__sort_order",
                                "vehicle_kind__name",
                                "container_number",
                            )
                        )
                    self.fields["container_passport"].queryset = passport_qs
                self._apply_activity_field_modes(activity_id_int)
            else:
                if self._is_edit:
                    self.fields["container_passport"].queryset = ContainerPassport.objects.none()
        else:
            if self._is_edit:
                self.fields["container_passport"].queryset = ContainerPassport.objects.none()

        if self._is_edit and self.instance.pk and self.instance.container_passport_id:
            cp_id = self.instance.container_passport_id
            cp_qs = self.fields["container_passport"].queryset
            if not cp_qs.filter(pk=cp_id).exists():
                passport_pks = list(cp_qs.values_list("pk", flat=True))
                passport_pks.append(cp_id)
                self.fields["container_passport"].queryset = (
                    ContainerPassport.objects.filter(pk__in=passport_pks)
                    .select_related("vehicle_kind")
                    .order_by(
                        "vehicle_kind__sort_order",
                        "vehicle_kind__name",
                        "container_number",
                    )
                )

        if self._is_edit:

            def _passport_label(obj):
                vk = obj.vehicle_kind
                short = (vk.shortcut or "").strip()
                base = obj.container_number or ""
                return f"{base} ({short})" if short else base

            self.fields["container_passport"].label_from_instance = _passport_label
            self.fields["container_passport"].help_text = (
                "Volitelně podle činnosti a RZ; výběrem se doplní číslo kontejneru (1)."
            )

        existing_attachment_count = 0
        if self._is_edit and self.instance and self.instance.pk:
            existing_attachment_count = self.instance.attachments.count()
        upload_slots = (
            MAX_PRUVODKA_ATTACHMENTS
            if not self._is_edit
            else remaining_attachment_slots(self.instance)
        )
        if upload_slots:
            att_attrs = {"accept": ".pdf,.jpg,.jpeg,.png,.doc,.docx,application/pdf"}
            for i in range(1, upload_slots + 1):
                field_name = f"attachment_{i}"
                label = (
                    f"Příloha {existing_attachment_count + i}"
                    if self._is_edit
                    else f"Příloha {i}"
                )
                self.fields[field_name] = forms.FileField(
                    required=False,
                    label=label,
                    widget=forms.ClearableFileInput(attrs=att_attrs),
                )
                self.attachment_upload_slots.append(i)

        self._apply_vehicle_rz_labels()

        self.fields["vehicle_rz"].help_text = "Nabídka se filtruje podle vybrané činnosti."
        self.fields["driver"].help_text = (
            "Nabídka řidičů se načítá podle vybrané činnosti (zpětně přes druhy vozidel)."
        )
        selected_waste_type = self.cleaned_data.get("waste_type") if hasattr(self, "cleaned_data") else None
        if not selected_waste_type:
            waste_type_id = (self.data.get("waste_type") or "").strip() if hasattr(self, "data") and self.data else ""
            if waste_type_id:
                try:
                    selected_waste_type = self.fields["waste_type"].queryset.filter(pk=int(waste_type_id)).first()
                except ValueError:
                    selected_waste_type = None
        if not selected_waste_type and self.initial.get("waste_type"):
            try:
                selected_waste_type = self.fields["waste_type"].queryset.filter(
                    pk=int(self.initial["waste_type"])
                ).first()
            except (TypeError, ValueError):
                selected_waste_type = None
        if not selected_waste_type and self.instance and self.instance.pk:
            selected_waste_type = self.instance.waste_type

        if selected_waste_type:
            self.fields["waste_code_display"].initial = (
                normalize_waste_catalog_code(selected_waste_type.code) or selected_waste_type.code or ""
            )
            self.fields["waste_category_display"].initial = selected_waste_type.category

        if self.instance and self.instance.pk:
            fulfillment_initial = _fulfillment_value_for_item(self.instance)
            if fulfillment_initial:
                self.fields["fulfillment_address_value"].initial = fulfillment_initial

        act_for_skip = None
        if activity_id:
            try:
                act_for_skip = ActivityCatalog.objects.filter(pk=int(activity_id)).first()
            except ValueError:
                pass
        if not has_follow_up_option(act_for_skip):
            self.fields["skip_follow_up"].widget = forms.HiddenInput()
            self.fields["skip_follow_up"].required = False

        if not follow_parent_pk or self._is_edit:
            self.fields["follow_up_vehicle_rz_manual"].widget = forms.HiddenInput()
            self.fields["follow_up_vehicle_rz_manual"].required = False

    def _apply_activity_field_modes(self, activity_id: int) -> None:
        def _req(key: str) -> bool:
            return get_effective_mode(activity_id, key) == ActivityFieldMode.REQUIRED

        def _off(key: str) -> bool:
            return get_effective_mode(activity_id, key) == ActivityFieldMode.OFF

        self.fields["suffix"].required = _req(ActivityFieldKey.SUFFIX)
        if _off(ActivityFieldKey.SUFFIX):
            self.fields["suffix"].required = False

        self.fields["vehicle_rz"].required = _req(ActivityFieldKey.VEHICLE_RZ)
        if _off(ActivityFieldKey.VEHICLE_RZ):
            self.fields["vehicle_rz"].required = False

        self.fields["driver"].required = _req(ActivityFieldKey.DRIVER)
        if _off(ActivityFieldKey.DRIVER):
            self.fields["driver"].required = False
        elif not self._is_edit:
            self.fields["driver"].required = True

        self.fields["container_number"].required = _req(ActivityFieldKey.CONTAINER_1)
        if _off(ActivityFieldKey.CONTAINER_1):
            self.fields["container_number"].required = False
            if "container_passport" in self.fields:
                self.fields["container_passport"].widget = forms.HiddenInput()

        self.fields["container_number_2"].required = _req(ActivityFieldKey.CONTAINER_2)
        if _off(ActivityFieldKey.CONTAINER_2):
            self.fields["container_number_2"].required = False

        self.fields["contact_phone"].required = _req(ActivityFieldKey.CONTACT_PHONE)
        if _off(ActivityFieldKey.CONTACT_PHONE):
            self.fields["contact_phone"].required = False

        self.fields["contract_number"].required = _req(ActivityFieldKey.CONTRACT_NUMBER)
        if _off(ActivityFieldKey.CONTRACT_NUMBER):
            self.fields["contract_number"].required = False

        self.fields["contact_note"].required = _req(ActivityFieldKey.CONTACT_NOTE)
        if _off(ActivityFieldKey.CONTACT_NOTE):
            self.fields["contact_note"].required = False

        self.fields["waste_type"].required = _req(ActivityFieldKey.WASTE_TYPE)

        self.fields["fulfillment_address_value"].required = _req(ActivityFieldKey.FULFILLMENT_ADDRESS)
        if _off(ActivityFieldKey.FULFILLMENT_ADDRESS):
            self.fields["fulfillment_address_value"].required = False

    def clean_drive_date(self):
        if getattr(self, "_yard_drive_date_locked", False):
            return timezone.localdate()
        return self.cleaned_data.get("drive_date")

    def clean_contact_phone(self):
        raw = (self.cleaned_data.get("contact_phone") or "").strip()
        if not raw:
            return ""
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) < 9:
            raise forms.ValidationError("Telefon musí mít alespoň 9 číslic (např. 000 000 000).")
        return format_czech_contact_phone(raw)

    def clean_attachment_1(self):
        return self._clean_attachment_upload("attachment_1")

    def clean_attachment_2(self):
        return self._clean_attachment_upload("attachment_2")

    def clean_attachment_3(self):
        return self._clean_attachment_upload("attachment_3")

    def _clean_attachment_upload(self, field_name: str):
        f = self.cleaned_data.get(field_name)
        if not f:
            return f
        ext = os.path.splitext(getattr(f, "name", "") or "")[1].lower()
        if ext not in ALLOWED_ATTACHMENT_EXTS:
            raise forms.ValidationError("Povolené přílohy: PDF, JPG, PNG, DOC, DOCX.")
        return f

    def clean(self):
        self._resolved_source_pair = None
        cleaned = super().clean()
        if self._is_edit and self.instance and self.instance.pk:
            existing = self.instance.attachments.count()
            new_count = sum(
                1
                for slot in self.attachment_upload_slots
                if cleaned.get(f"attachment_{slot}")
            )
            if existing + new_count > MAX_PRUVODKA_ATTACHMENTS:
                self.add_error(
                    None,
                    f"K jízdě lze uložit maximálně {MAX_PRUVODKA_ATTACHMENTS} přílohy celkem.",
                )
        subj_yard_early = None
        if self._request_user and is_sberny_dvur_role(self._request_user):
            subj_yard_early = get_sberny_dvur_subject(self._request_user)

        if getattr(self, "_yard_standalone_mode", False) and subj_yard_early:
            wt = cleaned.get("waste_type")
            suf = cleaned.get("suffix")
            if wt and suf:
                pair_row = yard_new_date_matrix_ready_qs(subj_yard_early).filter(
                    waste_type=wt,
                    suffix=suf,
                ).first()
                if not pair_row:
                    self.add_error(
                        None,
                        "Tato kombinace druhu odpadu a koncovky není mezi řádky bez „Svoz (matice)“ "
                        "(nezaškrtnutá matice svozu, druh vozidla a činnost).",
                    )
                else:
                    eff = pair_row.effective_yard_pruvodka_activity_id()
                    if not eff:
                        self.add_error(
                            None,
                            "V číselníku F/P u řádku doplňte činnost (svoz z dvora nebo průvodka z dvora).",
                        )
                    else:
                        cleaned["activity"] = ActivityCatalog.objects.get(pk=eff)

        activity = cleaned.get("activity")
        if not activity:
            return cleaned
        aid = activity.pk

        raw_f = normalize_fulfillment_address((cleaned.get("fulfillment_address_value") or "").strip())
        mode_f = get_effective_mode(aid, ActivityFieldKey.FULFILLMENT_ADDRESS)
        if mode_f == ActivityFieldMode.OFF:
            cleaned["fulfillment_address_value"] = ""
        elif not raw_f:
            if mode_f == ActivityFieldMode.REQUIRED:
                self.add_error("fulfillment_address_value", "Adresa plnění je povinná.")
        elif not is_valid_fulfillment_address_strict(raw_f):
            self.add_error(
                "fulfillment_address_value",
                "Adresa plnění musí být ve formátu 'Ulice, číslo popisné, město'.",
            )
        else:
            cleaned["fulfillment_address_value"] = raw_f

        if get_effective_mode(aid, ActivityFieldKey.SUFFIX) == ActivityFieldMode.OFF:
            cleaned["suffix"] = None
        elif get_effective_mode(aid, ActivityFieldKey.SUFFIX) == ActivityFieldMode.REQUIRED and not cleaned.get(
            "suffix"
        ):
            self.add_error("suffix", "U této činnosti je koncovka povinná.")

        if get_effective_mode(aid, ActivityFieldKey.VEHICLE_RZ) == ActivityFieldMode.OFF:
            cleaned["vehicle_rz"] = None
            cleaned["container_passport"] = None
        elif get_effective_mode(aid, ActivityFieldKey.VEHICLE_RZ) == ActivityFieldMode.REQUIRED and not cleaned.get(
            "vehicle_rz"
        ):
            self.add_error("vehicle_rz", "RZ vozidla je u této činnosti povinná.")

        driver_mode = get_effective_mode(aid, ActivityFieldKey.DRIVER)
        if driver_mode == ActivityFieldMode.OFF:
            cleaned["driver"] = None
        elif not cleaned.get("driver"):
            if driver_mode == ActivityFieldMode.REQUIRED or not self._is_edit:
                self.add_error(
                    "driver",
                    "Vyberte řidiče ze seznamu."
                    if not self._is_edit
                    else "Řidič je u této činnosti povinný.",
                )

        if get_effective_mode(aid, ActivityFieldKey.CONTAINER_1) == ActivityFieldMode.OFF:
            cleaned["container_number"] = ""
            cleaned["container_passport"] = None
        elif get_effective_mode(aid, ActivityFieldKey.CONTAINER_1) == ActivityFieldMode.REQUIRED:
            num_ok = (cleaned.get("container_number") or "").strip()
            passport_ok = bool(cleaned.get("container_passport"))
            if not num_ok and not passport_ok:
                self.add_error("container_number", "Číslo kontejneru (1) je povinné (nebo vyberte pasport).")

        if get_effective_mode(aid, ActivityFieldKey.CONTAINER_2) == ActivityFieldMode.OFF:
            cleaned["container_number_2"] = ""
        elif get_effective_mode(aid, ActivityFieldKey.CONTAINER_2) == ActivityFieldMode.REQUIRED and not (
            cleaned.get("container_number_2") or ""
        ).strip():
            self.add_error("container_number_2", "Číslo kontejneru (2) je povinné.")

        pair_kind_ids: list[int] | None = getattr(self, "_svoz_pair_kind_ids", None)
        for fname, errmsg in iter_container_passport_validation_errors(
            cleaned=cleaned,
            activity_id=aid,
            vehicle_rz=cleaned.get("vehicle_rz"),
            instance_pk=self.instance.pk if self.instance.pk else None,
            task_vehicle_kind_ids=pair_kind_ids,
        ):
            target = fname
            if target == "container_passport" and target not in self.fields:
                target = "container_number"
            self.add_error(target, errmsg)

        if get_effective_mode(aid, ActivityFieldKey.CONTACT_PHONE) == ActivityFieldMode.REQUIRED and not (
            cleaned.get("contact_phone") or ""
        ).strip():
            self.add_error("contact_phone", "Telefon je u této činnosti povinný.")

        if get_effective_mode(aid, ActivityFieldKey.CONTRACT_NUMBER) == ActivityFieldMode.OFF:
            cleaned["contract_number"] = ""
        elif get_effective_mode(aid, ActivityFieldKey.CONTRACT_NUMBER) == ActivityFieldMode.REQUIRED and not (
            cleaned.get("contract_number") or ""
        ).strip():
            self.add_error("contract_number", "Číslo smlouvy je u této činnosti povinné.")

        if not cleaned.get("name"):
            raise forms.ValidationError(
                "Vyberte subjekt: zadejte IČO (pokud má) nebo název a zvolte položku z našeptávače."
            )
        if not cleaned.get("ico"):
            selected_profile = (
                NameSubjectProfile.objects.select_related("ico").filter(name_id=cleaned["name"].pk).first()
            )
            if selected_profile and selected_profile.ico_id:
                cleaned["ico"] = selected_profile.ico

        parent = cleaned.get("follow_up_parent")
        st_raw = ""
        if hasattr(self, "data") and self.data:
            st_raw = (self.data.get("svoz_task") or "").strip()
        repeat_count = 1 if self._is_edit else int(cleaned.get("repeat_count") or 1)
        if repeat_count > 1 and (parent or st_raw.isdigit()):
            self.add_error(
                "repeat_count",
                "Pro navazující jízdu nebo požadavek svozu lze založit pouze 1 jízdu najednou.",
            )

        subj_yard = subj_yard_early
        if subj_yard:
            name_obj_chk = cleaned.get("name")
            ico_obj_chk = cleaned.get("ico")
            if not name_obj_chk or name_obj_chk.pk != subj_yard.name_id:
                raise forms.ValidationError(
                    "Jako sběrný dvůr můžete založit jízdu jen pro přiřazený subjekt z číselníku."
                )
            if subj_yard.ico_id and (not ico_obj_chk or ico_obj_chk.pk != subj_yard.ico_id):
                raise forms.ValidationError("IČO musí odpovídat subjektu sběrného dvora.")

        waste_type = cleaned.get("waste_type")
        name_obj = cleaned.get("name")
        suffix_obj = cleaned.get("suffix")
        if get_effective_mode(aid, ActivityFieldKey.WASTE_TYPE) == ActivityFieldMode.REQUIRED and not waste_type:
            self.add_error("waste_type", "Druh odpadu je u této činnosti povinný.")

        if waste_type and name_obj:
            profile = (
                NameSubjectProfile.objects.filter(name_id=name_obj.pk)
                .prefetch_related("allowed_waste_types", "waste_suffix_pairs")
                .first()
            )
            if profile:
                pairs_scope = profile.waste_suffix_pairs.all()
                if profile.is_collection_yard and not st_raw.isdigit():
                    pairs_scope = pruvodka_new_date_pairs_qs(profile)
                if pairs_scope.exists() or profile.is_collection_yard:
                    if suffix_obj:
                        from catalogs.services.name_subject_pair_vehicle_kinds import (
                            pair_for_pruvodka_context,
                        )

                        candidate_qs = pairs_scope.filter(
                            waste_type_id=waste_type.pk,
                            suffix_id=suffix_obj.pk,
                        )
                        preferred_pair_id = getattr(
                            self.instance, "source_waste_suffix_pair_id", None
                        )
                        if parent:
                            parent_preferred = preferred_pair_id_for_follow_up(parent)
                            if parent_preferred:
                                preferred_pair_id = parent_preferred
                        pair_row = pair_for_pruvodka_context(
                            pairs_qs=candidate_qs.select_related(
                                "yard_vehicle_kind"
                            ).prefetch_related("yard_vehicle_kinds"),
                            subject_profile=profile,
                            waste_type_id=waste_type.pk,
                            suffix_id=suffix_obj.pk,
                            vehicle_rz=cleaned.get("vehicle_rz"),
                            container_passport=cleaned.get("container_passport"),
                            preferred_pair_id=preferred_pair_id,
                        )
                        if not pair_row:
                            if candidate_qs.exists():
                                self.add_error(
                                    "vehicle_rz",
                                    "Vybrané vozidlo nebo pasport kontejneru neodpovídá žádnému řádku "
                                    "„Povolené odpady a koncovky“ pro tento odpad a koncovku. "
                                    "Zvolte správné RZ nebo upravte číselník F/P.",
                                )
                            else:
                                raise forms.ValidationError(
                                    "Zvolená kombinace druh odpadu + koncovka není u subjektu v řádcích."
                                )
                        else:
                            manual_rz = (
                                _form_checkbox_truthy(self.data.get("follow_up_vehicle_rz_manual"))
                                if hasattr(self, "data") and self.data
                                else False
                            )
                            inherits_parent_pair = follow_up_inherits_parent_pair(
                                parent,
                                cleaned.get("vehicle_rz"),
                                manual_rz=manual_rz,
                            )
                            if inherits_parent_pair and parent.source_waste_suffix_pair_id:
                                parent_pair = parent.source_waste_suffix_pair
                                if parent_pair:
                                    pair_row = parent_pair
                            self._resolved_source_pair = pair_row
                            if (
                                subj_yard
                                and profile.pk == subj_yard.pk
                                and not getattr(self, "_yard_standalone_mode", False)
                                and pair_row.yard_svoz_enabled
                                and not st_raw.isdigit()
                            ):
                                raise forms.ValidationError(
                                    "Pro tento odpad a koncovku je u sběrného dvora zapnutá Svoz (matice) — "
                                    "na /waste-docs/new/ není povolena. Použijte požadavek na svoz nebo "
                                    "vypněte matici svozu u řádku v číselníku F/P."
                                )
                            # Běžná jízda: druh vozidla musí odpovídat řádku „Povolené odpady
                            # a koncovky“ (Druhy vozidla svoz). Svozový úkol a průvodka z dvora
                            # mají vlastní kontrolu níže; když u páru žádný druh není, výběr je volný.
                            is_svoz_task_ctx = st_raw.isdigit()
                            is_yard_standalone_ctx = bool(
                                subj_yard and getattr(self, "_yard_standalone_mode", False)
                            )
                            if (
                                not is_svoz_task_ctx
                                and not is_yard_standalone_ctx
                                and get_effective_mode(aid, ActivityFieldKey.VEHICLE_RZ)
                                != ActivityFieldMode.OFF
                            ):
                                from catalogs.services.name_subject_pair_vehicle_kinds import (
                                    pair_covering_vehicle_kind_ids,
                                    pair_has_vehicle_kinds,
                                    rz_profile_pair_mismatch_message,
                                )

                                if pair_has_vehicle_kinds(pair_row):
                                    vz_sel = cleaned.get("vehicle_rz")
                                    if vz_sel and not inherits_parent_pair:
                                        try:
                                            prof_sel = vz_sel.profile
                                        except ObjectDoesNotExist:
                                            prof_sel = None
                                        rz_label = (getattr(vz_sel, "value", None) or "").strip() or "—"
                                        mismatch = rz_profile_pair_mismatch_message(
                                            prof_sel, pair_row, vehicle_rz_label=rz_label
                                        )
                                        if mismatch:
                                            self.add_error("vehicle_rz", mismatch)
                    else:
                        if not profile.waste_suffix_pairs.filter(waste_type_id=waste_type.pk).exists():
                            raise forms.ValidationError(
                                "Zvolený druh odpadu není u subjektu v žádném řádku odpad + koncovka."
                            )
                else:
                    allowed_waste_ids = set(profile.allowed_waste_types.values_list("id", flat=True))
                    if allowed_waste_ids and waste_type.pk not in allowed_waste_ids:
                        raise forms.ValidationError(
                            "Zvolený druh odpadu není u subjektu mezi povolenými odpady."
                        )

        if activity.require_nitropodnikovy_subjekt and name_obj:
            profile = NameSubjectProfile.objects.filter(name_id=name_obj.pk).first()
            if (
                not profile
                or not profile.nitropodnikovy_subjekt
                or profile.is_municipality
            ):
                raise forms.ValidationError(
                    "U této činnosti musíte vybrat subjekt označený v číselníku jako nitropodnikový (ne obec)."
                )

        parent = cleaned.get("follow_up_parent")
        if parent:
            if self.instance.pk and parent.pk == self.instance.pk:
                self.add_error(
                    "follow_up_parent",
                    "Jízda nemůže navazovat sama na sebe.",
                )
            if self._request_user and (
                not can_see_all_waste_docs(self._request_user)
                and parent.created_by_id != self._request_user.id
            ):
                self.add_error(
                    "follow_up_parent",
                    "Na tuto návaznou jízdu nemáte oprávnění.",
                )
            existing_link = (
                self._is_edit
                and self.instance.pk
                and self.instance.follow_up_parent_id == parent.pk
            )
            if not existing_link:
                if cleaned.get("name") and parent.name_id != cleaned["name"].pk:
                    self.add_error(
                        "follow_up_parent",
                        "Návaznou jízdu lze propojit jen se stejným názvem F/P osoby.",
                    )
                expected_ids = allowed_follow_up_activity_ids(parent.activity if parent.activity_id else None)
                if activity.pk not in expected_ids:
                    self.add_error(
                        "follow_up_parent",
                        "Činnost této průvodky neodpovídá návaznosti vybraného záznamu.",
                    )
                if parent_has_terminal_child(parent):
                    self.add_error(
                        "follow_up_parent",
                        "Tato průvodka už má uzavírající navazující jízdu.",
                    )
                elif not parent.follow_up_open and not self._is_edit:
                    self.add_error(
                        "follow_up_parent",
                        "Tato průvodka už není označená jako čekající návaznost.",
                    )

        if parent:
            if not cleaned.get("vehicle_rz"):
                self.add_error("vehicle_rz", "U navazující jízdy je RZ vozidla povinná.")
            elif parent.vehicle_rz_id and not cleaned.get("follow_up_vehicle_rz_manual"):
                kind_err = follow_up_vehicle_kind_error(
                    parent_vehicle_rz=parent.vehicle_rz,
                    follow_vehicle_rz=cleaned.get("vehicle_rz"),
                )
                if kind_err:
                    self.add_error("vehicle_rz", kind_err)
            if not cleaned.get("driver"):
                self.add_error("driver", "U navazující jízdy je řidič povinný.")

        if st_raw.isdigit():
            from catalogs.services.name_subject_pair_vehicle_kinds import (
                pair_for_svoz_task_record,
                pair_vehicle_kind_ids,
                rz_profile_pair_mismatch_message,
            )

            st = (
                SvozTask.objects.filter(pk=int(st_raw), status=SvozTask.Status.OPEN)
                .select_related("vehicle_kind", "source_waste_suffix_pair")
                .first()
            )
            vz = cleaned.get("vehicle_rz")
            pair_st = pair_for_svoz_task_record(st) if st else None
            if pair_st:
                self._resolved_source_pair = pair_st
                self._svoz_pair_kind_ids = pair_vehicle_kind_ids(pair_st)
            if st and pair_st:
                if get_effective_mode(activity.pk, ActivityFieldKey.VEHICLE_RZ) != ActivityFieldMode.OFF:
                    if not vz:
                        self.add_error(
                            "vehicle_rz",
                            "U požadavku ze sběrného dvora zvolte RZ vozidla s požadovaným druhem vozidla.",
                        )
                    else:
                        try:
                            prof_rz = vz.profile
                        except ObjectDoesNotExist:
                            prof_rz = None
                        rz_label = (getattr(vz, "value", None) or "").strip() or "—"
                        mismatch = rz_profile_pair_mismatch_message(
                            prof_rz, pair_st, vehicle_rz_label=rz_label
                        )
                        if mismatch:
                            self.add_error("vehicle_rz", mismatch)

        if (
            subj_yard
            and getattr(self, "_yard_standalone_mode", False)
            and not st_raw.isdigit()
        ):
            wt_y = cleaned.get("waste_type")
            suf_y = cleaned.get("suffix")
            vz_y = cleaned.get("vehicle_rz")
            pair_yard = None
            if wt_y and suf_y:
                from catalogs.services.name_subject_pair_vehicle_kinds import (
                    pair_for_pruvodka_context,
                )

                pair_yard = pair_for_pruvodka_context(
                    pairs_qs=(
                        yard_new_date_matrix_ready_qs(subj_yard)
                        .filter(waste_type=wt_y, suffix=suf_y)
                        .select_related("yard_vehicle_kind")
                        .prefetch_related("yard_vehicle_kinds")
                    ),
                    vehicle_rz=vz_y,
                    container_passport=cleaned.get("container_passport"),
                    preferred_pair_id=getattr(
                        self.instance, "source_waste_suffix_pair_id", None
                    ),
                )
            if pair_yard:
                self._resolved_source_pair = pair_yard
                from catalogs.services.name_subject_pair_vehicle_kinds import (
                    pair_vehicle_kind_ids,
                    rz_profile_pair_mismatch_message,
                )

                self._svoz_pair_kind_ids = pair_vehicle_kind_ids(pair_yard)
                if get_effective_mode(activity.pk, ActivityFieldKey.VEHICLE_RZ) != ActivityFieldMode.OFF:
                    if not vz_y:
                        self.add_error(
                            "vehicle_rz",
                            "Zvolte RZ vozidla odpovídající druhu vozidla u řádku v číselníku F/P.",
                        )
                    else:
                        try:
                            prof_y = vz_y.profile
                        except ObjectDoesNotExist:
                            prof_y = None
                        rz_label = (getattr(vz_y, "value", None) or "").strip() or "—"
                        mismatch = rz_profile_pair_mismatch_message(
                            prof_y, pair_yard, vehicle_rz_label=rz_label
                        )
                        if mismatch:
                            self.add_error("vehicle_rz", mismatch)

        return cleaned

    def save(self, commit=True):
        item = super().save(commit=False)
        waste_type = item.waste_type
        fulfillment_address = normalize_fulfillment_address(
            (self.cleaned_data.get("fulfillment_address_value") or "").strip()
        )
        if fulfillment_address:
            item.address = AddressCatalog.objects.get_or_create(value=fulfillment_address)[0]
        else:
            item.address = AddressCatalog.objects.get_or_create(value="—")[0]
        if waste_type:
            code_value = (waste_type.code or "").strip() or "Neuvedeno"
            category_value = (waste_type.category or "").strip() or "Neuvedeno"
            item.waste_code = WasteCodeCatalog.objects.get_or_create(value=code_value)[0]
            item.waste_category = WasteCategoryCatalog.objects.get_or_create(value=category_value)[0]
        cp_save = self.cleaned_data.get("container_passport")
        if cp_save:
            item.container_number = cp_save.container_number
        item.source_waste_suffix_pair = getattr(self, "_resolved_source_pair", None)
        if commit:
            item.save()
            self.save_m2m()
        return item

    def _apply_vehicle_rz_labels(self):
        def _label(obj):
            note = ""
            kinds = ""
            try:
                profile = obj.profile
                note = (profile.vehicle_type or "").strip()
                kinds = ", ".join(
                    profile.vehicle_kinds.exclude(shortcut="").values_list("shortcut", flat=True).distinct()
                )
            except ObjectDoesNotExist:
                note = ""
                kinds = ""
            details = " | ".join(part for part in [note, f"Druh: {kinds}" if kinds else ""] if part)
            return f"{obj.value} - {details}" if details else obj.value

        self.fields["vehicle_rz"].label_from_instance = _label
