from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from catalogs.forms.name_subject import _attach_native_tooltips
from catalogs.forms.pair_file_widget import PairClearableFileInput
from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    VehicleKindCatalog,
    ZpoDocument,
)
from catalogs.services.fulfillment_address import (
    is_valid_fulfillment_address_strict,
    normalize_fulfillment_address,
)
from catalogs.services.pair_fulfillment_address import central_fulfillment_address_value
from catalogs.services.name_subject_pair_vehicle_kinds import sync_pair_primary_vehicle_kind_fk
from catalogs.services.suffix_catalog_scope import suffix_catalog_queryset_for_subject_pair_select
from catalogs.services.vehicle_kind_display import bind_vehicle_kind_select_labels
from catalogs.waste_catalog_code import normalize_waste_catalog_code
from pio.services.archive import archive_pair_pio_document
from pio.validators import validate_pio_upload_size


def _waste_label(obj):
    code = normalize_waste_catalog_code(obj.code)
    return f"{code} — {obj.value}" if code else obj.value


class NameSubjectWasteSuffixPairForm(forms.ModelForm):
    fulfillment_address_value = forms.CharField(
        label="Adresa plnění",
        max_length=255,
        required=False,
    )

    class Meta:
        model = NameSubjectWasteSuffixPair
        fields = (
            "sort_order",
            "waste_type",
            "suffix",
            "yard_svoz_enabled",
            "yard_vehicle_kinds",
            "yard_svoz_activity",
            "yard_svoz_display_label",
            "yard_dispatch_note_enabled",
            "yard_dispatch_note_title",
            "yard_dispatch_note_text",
            "yard_svoz_auto_assign_driver",
            "yard_svoz_exception_slot",
            "yard_pruvodka_enabled",
            "yard_pruvodka_activity",
            "yard_container_kind",
            "contract_number",
            "ride_note",
            "zpo",
            "suppress_system_zpo",
            "pio_document",
            "other_document",
        )
        labels = {
            "sort_order": "Pořadí",
            "waste_type": "Druh odpadu",
            "suffix": "Koncovka",
            "yard_svoz_enabled": "Svoz (matice)",
            "yard_vehicle_kinds": "Druhy vozidla (svoz)",
            "yard_svoz_activity": "Činnost (svoz)",
            "yard_svoz_display_label": "Název v matici požadavku",
            "yard_dispatch_note_enabled": "Poznámka pro dispečera",
            "yard_dispatch_note_title": "Název poznámky",
            "yard_dispatch_note_text": "Text poznámky",
            "yard_svoz_auto_assign_driver": "Běžný svoz (řádek v plánu dvora)",
            "yard_svoz_exception_slot": "Výjimka — slot plánu (V1–V4)",
            "yard_pruvodka_enabled": "Průvodka z dvora",
            "yard_pruvodka_activity": "Činnost (průvodka)",
            "yard_container_kind": "Druh kontejneru",
            "contract_number": "Číslo smlouvy",
            "ride_note": "Poznámka",
            "zpo": "ZPO z knihovny",
            "suppress_system_zpo": "Vypnout syst. ZPO (pár)",
            "pio_document": "PIO",
            "other_document": "Jiný dokument",
        }
        help_texts = {
            "waste_type": (
                "Druh odpadu z číselníku (kód Katalog odpadů, např. 20 03 01). Spolu s koncovkou určuje jeden "
                "povolený pár u tohoto subjektu: v průvodce u daného subjektu uvidíte u tohoto odpadu jen tyto koncovky."
            ),
            "suffix": (
                "Koncové zařízení z číselníku (např. překladiště, provozovna). Stejný odpad může mít u subjektu více "
                "řádků s různými koncovkami. V průvodce se nabízejí jen koncovky povolené pro subjekt a zvolený odpad."
            ),
            "yard_svoz_enabled": (
                "Zapne tento pár odpad + koncovka v matici požadavku na svoz u sběrného dvora. Dvůr pak může zadávat "
                "poptávku na svoz (fronta před průvodkami) pro tuto kombinaci."
            ),
            "yard_vehicle_kinds": (
                "Vyberte jeden nebo více druhů (Ctrl+klik), např. jen Hák (H), nebo H i 3H. "
                "Sílu vozidel (H → 3H) nastavíte v číselníku druhů vozidel — pole Nadřazený druh."
            ),
            "yard_svoz_activity": (
                "Jaká činnost se u svozu vykonává (např. výměna kontejneru). Předvyplní se tam, kde aplikace pracuje "
                "s činností u svozu a v průvodce."
            ),
            "yard_svoz_display_label": (
                "Vlastní text řádku v matici požadavku pro sběrný dvůr. Když je prázdné, zobrazí se název z číselníku "
                "druhu odpadu. Ukládá se stále stejný druh odpadu a koncovka — jde jen o popisek pro dispečink/dvůr."
            ),
            "yard_dispatch_note_enabled": (
                "Po odeslání matice ze sběrného dvora vytvořit jednorázovou poznámku v panelu dispečera "
                "(blikající upozornění). Vyžaduje vyplněný název poznámky."
            ),
            "yard_dispatch_note_title": (
                "Název jednorázové poznámky v panelu dispečera. Použije se jen při zapnuté volbě „Poznámka pro dispečera“."
            ),
            "yard_dispatch_note_text": (
                "Text poznámky pro dispečera. K němu se automaticky doplní kontejnery a poznámka ze dvora, pokud je zadána."
            ),
            "yard_svoz_auto_assign_driver": (
                "Zapnuto: řádek patří do běžného fondu řidičů dvora v Plánu svozů. Vypnuto: výjimka — v Plánu svozů vyplňte řidiče ve sloupci V1–V4 podle zvoleného slotu."
            ),
            "yard_svoz_exception_slot": (
                "Pouze u výjimky (vypnutý běžný svoz): který sloupec V1–V4 obsluhuje kontejnery z tohoto řádku matice. "
                "Na jeden dvůr a druh vozidla smí být každý slot jen jednou."
            ),
            "yard_pruvodka_enabled": (
                "Povolí uživateli v roli sběrný dvůr založit průvodku přímo z dvora pro tento konkrétní pár odpad + koncovka."
            ),
            "yard_pruvodka_activity": (
                "Činnost zapsaná v průvodce z dvora. Když nevyplníte, použije se činnost u svozu, pokud je vyplněná."
            ),
            "yard_container_kind": (
                "Nápověda u matice požadavku (standardní kontejner, lis, velkoobjem…). Volitelné; sloučí se se zobrazením "
                "pro dvůr, nezakládá samostatnou evidenci kontejnerů."
            ),
            "contract_number": (
                "Číslo smlouvy vázané na tento pár odpad + koncovka. Použije se tam, kde se u odpadu pracuje se smlouvou."
            ),
            "ride_note": (
                "Sem pište pokyn k jízdě (čas, výška, výměna, kontakt…). "
                "Po výběru odpadu a koncovky se text načte do požadavku i do poznámky jízdy."
            ),
            "fulfillment_address_value": (
                "Vyberte z nabídky (centrální adresa subjektu a adresy z ostatních řádků), zadejte ručně "
                "nebo použijte mapu. Prázdné pole = použije se centrální adresa plnění subjektu."
            ),
            "suppress_system_zpo": (
                "Jen u tohoto páru: vypne systémové generování ZPO k jízdám (přebije obecné nastavení „Generovat systémové ZPO“ u subjektu)."
            ),
            "zpo": (
                "Vyberte soubor ZPO ze sdílené knihovny (Číselníky → Knihovna ZPO). Nový dokument lze přidat tlačítkem pod výběrem."
            ),
            "pio_document": (
                "Nahraný soubor PIO u tohoto páru. Maximální velikost určuje nastavení aplikace. "
                "Pro přesun do archivu zaškrtněte „Přesunout PIO do archivu“ a uložte — soubor zůstane v Archivu PIO, pole se uvolní."
            ),
            "other_document": (
                "Další soubor u páru (např. smlouva, doložka), bez vazby na typ ZPO/PIO. "
                "Pro odstranění zaškrtněte „Odstranit dokument“ a uložte formulář."
            ),
        }
        widgets = {
            "yard_vehicle_kinds": forms.SelectMultiple(
                attrs={
                    "size": 6,
                    "style": "font-size:1rem; min-height:9rem; border:2px solid #c0392b; border-radius:8px;",
                }
            ),
            "sort_order": forms.HiddenInput(),
            "yard_svoz_display_label": forms.TextInput(
                attrs={
                    "maxlength": "200",
                    "placeholder": "Volitelné; prázdné = název z číselníku",
                    "class": "name-subject-pairs__matrix-label-input",
                }
            ),
            "yard_dispatch_note_title": forms.TextInput(
                attrs={"maxlength": "160", "placeholder": "Volitelné; po hlášení ze dvora"}
            ),
            "yard_dispatch_note_text": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Volitelná šablona pro dispečera"}
            ),
            "fulfillment_address_value": forms.TextInput(
                attrs={
                    "maxlength": "255",
                    "placeholder": "Centrální adresa subjektu (nebo vyberte / zadejte jinou)",
                    "class": "name-subject-pairs__fulfillment-address-input",
                    "autocomplete": "off",
                    "title": "Našeptávač jako u Adresa plnění výše; formát Ulice, č.p., Město.",
                }
            ),
            "zpo": forms.Select(attrs={"class": "name-subject-pairs__zpo-select"}),
        }

    def __init__(self, *args, show_dispatch_plan_fields=True, actor_user=None, subject_profile=None, **kwargs):
        self.show_dispatch_plan_fields = show_dispatch_plan_fields
        self.actor_user = actor_user
        self.subject_profile = subject_profile
        super().__init__(*args, **kwargs)
        self.fields["waste_type"].queryset = self.fields["waste_type"].queryset.order_by("code", "value")
        self.fields["waste_type"].label_from_instance = _waste_label
        must_suffix = set()
        inst = self.instance
        if inst:
            if getattr(inst, "suffix_id", None):
                must_suffix.add(inst.suffix_id)
        if self.is_bound:
            raw = self.data.get(self.add_prefix("suffix"))
            if raw not in (None, ""):
                try:
                    must_suffix.add(int(raw))
                except (TypeError, ValueError):
                    pass
        suffix_qs = suffix_catalog_queryset_for_subject_pair_select(must_include_ids=must_suffix)
        self.fields["suffix"].queryset = suffix_qs
        self.fields["suppress_system_zpo"].required = False
        self.fields["yard_svoz_enabled"].required = False
        self.fields["yard_pruvodka_enabled"].required = False
        self.fields["yard_vehicle_kinds"].queryset = VehicleKindCatalog.objects.order_by("sort_order", "name")
        bind_vehicle_kind_select_labels(self, "yard_vehicle_kinds")
        self.fields["yard_vehicle_kinds"].required = False
        if self.instance and self.instance.pk:
            self.fields["yard_vehicle_kinds"].initial = list(
                self.instance.yard_vehicle_kinds.values_list("pk", flat=True)
            )
        self.fields["yard_svoz_activity"].queryset = ActivityCatalog.objects.order_by("name")
        self.fields["yard_svoz_activity"].required = False
        self.fields["yard_pruvodka_activity"].queryset = ActivityCatalog.objects.order_by("name")
        self.fields["yard_pruvodka_activity"].required = False
        self.fields["yard_svoz_display_label"].required = False
        self.fields["yard_dispatch_note_enabled"].required = False
        self.fields["yard_dispatch_note_title"].required = False
        self.fields["yard_dispatch_note_text"].required = False
        self.fields["yard_svoz_auto_assign_driver"].required = False
        if not self.show_dispatch_plan_fields:
            self.fields.pop("yard_svoz_exception_slot", None)
        else:
            self.fields["yard_svoz_exception_slot"].required = False
            self.fields["yard_svoz_exception_slot"].widget = forms.Select(
                attrs={"class": "name-subject-pairs__exception-slot-select"},
                choices=[("", "— slot —"), (1, "V1"), (2, "V2"), (3, "V3"), (4, "V4")],
            )
        zpo_field = self.fields["zpo"]
        zpo_field.queryset = ZpoDocument.objects.order_by("label", "id")
        zpo_field.required = False
        zpo_field.empty_label = "— bez ZPO —"
        pio_widget = PairClearableFileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png"})
        pio_widget.clear_checkbox_label = "Přesunout PIO do archivu"
        self.fields["pio_document"].widget = pio_widget
        other_widget = PairClearableFileInput()
        other_widget.clear_checkbox_label = "Odstranit dokument"
        self.fields["other_document"].widget = other_widget
        so = self.fields.get("sort_order")
        if so:
            so.required = False
        delete_f = self.fields.get("DELETE")
        if delete_f is not None:
            delete_f.help_text = (
                "Označí celý řádek páru odpad + koncovka ke smazání. Pár se skutečně odstraní až po kliknutí na Uložit."
            )
        _attach_native_tooltips(self)
        ff_widget = self.fields["fulfillment_address_value"].widget
        ff_class = ff_widget.attrs.get("class", "")
        if "name-subject-pairs__fulfillment-address-input" not in ff_class:
            ff_widget.attrs["class"] = (ff_class + " name-subject-pairs__fulfillment-address-input").strip()
        if self.instance and self.instance.pk and self.instance.fulfillment_address_id:
            self.fields["fulfillment_address_value"].initial = self.instance.fulfillment_address.value

    def clean_fulfillment_address_value(self):
        value = normalize_fulfillment_address(
            (self.cleaned_data.get("fulfillment_address_value") or "").strip()
        )
        if value and not is_valid_fulfillment_address_strict(value):
            raise forms.ValidationError(
                "Adresa plnění musí být ve tvaru Ulice, č.p., Město nebo Město č.p."
            )
        profile = self.subject_profile or getattr(self.instance, "subject_profile", None)
        if value and profile:
            central = normalize_fulfillment_address(central_fulfillment_address_value(profile))
            if central and value == central:
                return ""
        return value

    def clean_pio_document(self):
        f = self.cleaned_data.get("pio_document")
        if f:
            validate_pio_upload_size(f)
        return f

    def clean_sort_order(self):
        value = self.cleaned_data.get("sort_order")
        if value in (None, ""):
            if self.instance and self.instance.pk:
                return int(getattr(self.instance, "sort_order", 0) or 0)
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            if self.instance and self.instance.pk:
                return int(getattr(self.instance, "sort_order", 0) or 0)
            return 0

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("yard_pruvodka_enabled"):
            if not (cleaned.get("yard_pruvodka_activity") or cleaned.get("yard_svoz_activity")):
                raise forms.ValidationError(
                    "U zapnuté průvodky z dvora vyberte činnost pro průvodku nebo vyplňte činnost u svozu."
                )
        if cleaned.get("yard_svoz_enabled"):
            kinds = cleaned.get("yard_vehicle_kinds")
            if not kinds:
                self.add_error(
                    "yard_vehicle_kinds",
                    "U zapnutého svozu vyberte alespoň jeden druh vozidla (nebo svoz vypněte).",
                )
        if "yard_svoz_exception_slot" in self.fields:
            is_exception = cleaned.get("yard_svoz_enabled") and not cleaned.get(
                "yard_svoz_auto_assign_driver", True
            )
            slot = cleaned.get("yard_svoz_exception_slot")
            if is_exception:
                if slot is None:
                    self.add_error(
                        "yard_svoz_exception_slot",
                        "U výjimky vyberte slot V1–V4 v plánu svozů (dispečink).",
                    )
                elif slot not in (1, 2, 3, 4):
                    self.add_error("yard_svoz_exception_slot", "Slot musí být V1, V2, V3 nebo V4.")
            elif slot is not None:
                cleaned["yard_svoz_exception_slot"] = None
        if cleaned.get("yard_dispatch_note_enabled"):
            if not (cleaned.get("yard_dispatch_note_title") or "").strip():
                self.add_error(
                    "yard_dispatch_note_title",
                    "Vyplňte název poznámky, pokud má poznámka pro dispečera vznikat.",
                )
        return cleaned

    def save(self, commit=True):
        clear_pio = self.cleaned_data.get("pio_document") is False or bool(
            self.data.get(self.add_prefix("pio_document-clear")) if self.is_bound else False
        )
        if clear_pio and self.instance.pk:
            from catalogs.models import NameSubjectWasteSuffixPair

            pair = NameSubjectWasteSuffixPair.objects.get(pk=self.instance.pk)
            if pair.pio_document and getattr(pair.pio_document, "name", ""):
                archive_pair_pio_document(
                    pair,
                    note="Přesunuto z aktivního PIO u páru (formulář subjektu)",
                    created_by=self.actor_user,
                )
            self.instance.refresh_from_db()

        inst = super().save(commit=False)
        inst.ride_note = (self.cleaned_data.get("ride_note") or "").strip()
        fulfillment_address_value = (self.cleaned_data.get("fulfillment_address_value") or "").strip()
        if fulfillment_address_value:
            inst.fulfillment_address = AddressCatalog.objects.get_or_create(value=fulfillment_address_value)[0]
        else:
            inst.fulfillment_address = None
        if commit:
            inst.save()
            self.save_m2m()
            sync_pair_primary_vehicle_kind_fk(inst)
        return inst

    def has_changed(self):
        if self.is_bound:
            if self.data.get(self.add_prefix("DELETE")):
                return True
            if self.data.get(self.add_prefix("pio_document-clear")):
                return True
            if self.data.get(self.add_prefix("other_document-clear")):
                return True
        changed = super().has_changed()
        if not changed:
            return False
        if self.instance and self.instance.pk:
            return True
        if not self.is_bound:
            return False
        waste_raw = (self.data.get(self.add_prefix("waste_type")) or "").strip()
        suffix_raw = (self.data.get(self.add_prefix("suffix")) or "").strip()
        delete_raw = self.data.get(self.add_prefix("DELETE"))
        if delete_raw:
            return True

        zpo_raw = (self.data.get(self.add_prefix("zpo")) or "").strip()
        yard_vehicle_kinds_raw = self.data.getlist(self.add_prefix("yard_vehicle_kinds"))
        yard_vehicle_kind_raw = yard_vehicle_kinds_raw or (
            self.data.get(self.add_prefix("yard_vehicle_kind")) or ""
        ).strip()
        yard_svoz_activity_raw = (self.data.get(self.add_prefix("yard_svoz_activity")) or "").strip()
        yard_pruvodka_activity_raw = (self.data.get(self.add_prefix("yard_pruvodka_activity")) or "").strip()
        yard_container_kind_raw = (self.data.get(self.add_prefix("yard_container_kind")) or "").strip()
        contract_number_raw = (self.data.get(self.add_prefix("contract_number")) or "").strip()
        ride_note_raw = (self.data.get(self.add_prefix("ride_note")) or "").strip()
        yard_svoz_display_label_raw = (self.data.get(self.add_prefix("yard_svoz_display_label")) or "").strip()

        has_core_values = bool(
            waste_raw
            or suffix_raw
            or zpo_raw
            or yard_vehicle_kind_raw
            or yard_svoz_activity_raw
            or yard_pruvodka_activity_raw
            or yard_container_kind_raw
            or contract_number_raw
            or ride_note_raw
            or yard_svoz_display_label_raw
        )
        return has_core_values


class NameSubjectWasteSuffixPairFormSetBase(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        self.form_kwargs = kwargs.pop("form_kwargs", {})
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs.update(self.form_kwargs)
        return super()._construct_form(i, **kwargs)

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        seen: dict[tuple[int, int], int] = {}
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            cd = form.cleaned_data
            if not cd or cd.get("DELETE"):
                continue
            if not cd.get("yard_svoz_enabled") or cd.get("yard_svoz_auto_assign_driver", True):
                continue
            slot = cd.get("yard_svoz_exception_slot")
            if slot is None:
                continue
            kinds = cd.get("yard_vehicle_kinds")
            vk_id = None
            if kinds:
                vk_id = min(k.pk for k in kinds)
            elif form.instance and form.instance.yard_vehicle_kind_id:
                vk_id = form.instance.yard_vehicle_kind_id
            if vk_id is None:
                continue
            key = (int(vk_id), int(slot))
            if key in seen:
                form.add_error(
                    "yard_svoz_exception_slot",
                    f"Slot V{slot} je u tohoto druhu vozidla už použitý u jiného výjimkového řádku.",
                )
            else:
                seen[key] = form.instance.pk if form.instance.pk else 0


NameSubjectWasteSuffixPairFormSet = inlineformset_factory(
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    form=NameSubjectWasteSuffixPairForm,
    formset=NameSubjectWasteSuffixPairFormSetBase,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
    max_num=50,
)
