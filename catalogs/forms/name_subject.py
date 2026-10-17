from django import forms
from django.urls import reverse
from django.utils.html import format_html

from catalogs.models import (
    AddressCatalog,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    SuffixCatalog,
    WasteTypeCatalog,
)
from catalogs.services import normalize_czech_address
from catalogs.services.phone import format_czech_contact_phone
from catalogs.services.fulfillment_address import (
    is_valid_fulfillment_address_strict,
    normalize_fulfillment_address,
)
from users.services.access_profile import get_access_profile
from catalogs.services.subject_satellites import clear_subject_pio_profile_fields, save_related_satellites


def _attach_native_tooltips(form: forms.BaseForm) -> None:
    """Nastaví atribut title (tooltip) z help_text u viditelných widgetů."""
    for _name, field in form.fields.items():
        if isinstance(field.widget, forms.HiddenInput):
            continue
        tip = (field.help_text or "").strip()
        if tip:
            field.widget.attrs.setdefault("title", tip)


class NameSubjectProfileForm(forms.ModelForm):
    name_value = forms.CharField(label="Název F/P osoby", max_length=255)
    ico_value = forms.CharField(label="IČO", max_length=8, required=False)
    facility_address_value = forms.CharField(label="Adresa provozovny", max_length=255, required=False)
    fulfillment_address_value = forms.CharField(label="Adresa plnění", max_length=255, required=False)
    facility_latitude = forms.DecimalField(required=False, max_digits=10, decimal_places=7, widget=forms.HiddenInput())
    facility_longitude = forms.DecimalField(required=False, max_digits=10, decimal_places=7, widget=forms.HiddenInput())
    fulfillment_latitude = forms.DecimalField(required=False, max_digits=10, decimal_places=7, widget=forms.HiddenInput())
    fulfillment_longitude = forms.DecimalField(required=False, max_digits=10, decimal_places=7, widget=forms.HiddenInput())

    is_collection_yard = forms.BooleanField(required=False, label="Lokalita sběrného dvora")
    yard_allow_pruvodka = forms.BooleanField(required=False, label="Povolit průvodku z dvora")
    yard_allow_matrix = forms.BooleanField(required=False, label="Povolit matici požadavků")
    yard_svoz_dispatch_group = forms.CharField(max_length=120, required=False, label="Skupina v plánu svozů")
    system_generates_zpo = forms.BooleanField(
        required=False,
        initial=True,
        label="Generovat systémové ZPO k jízdám",
    )
    contact_phone = forms.CharField(required=False, max_length=20, label="Telefon")
    contact_note = forms.CharField(required=False, max_length=200, label="Poznámka", widget=forms.Textarea(attrs={"rows": 2}))
    fulfillment_orp = forms.CharField(max_length=120, required=False, label="ORP Adresa plnění (Obec s rozšířenou působností)")
    fulfillment_iczuj = forms.CharField(max_length=20, required=False, label="IČZÚJ (identifikační číslo základní územní jednotky)")
    pio_officer_name = forms.CharField(max_length=255, required=False, label="PIO — jméno odpovědné osoby")
    pio_officer_phone = forms.CharField(max_length=20, required=False, label="PIO — telefon osoby")
    pio_officer_email = forms.EmailField(required=False, label="PIO — e-mail")
    pio_waste_type = forms.ModelChoiceField(
        queryset=WasteTypeCatalog.objects.all(),
        required=False,
        label="PIO — druh odpadu",
    )
    pio_suffix = forms.ModelChoiceField(
        queryset=SuffixCatalog.objects.all(),
        required=False,
        label="PIO — koncovka",
    )
    pio_outside_map_lat = forms.DecimalField(required=False, max_digits=10, decimal_places=7, widget=forms.HiddenInput())
    pio_outside_map_lng = forms.DecimalField(required=False, max_digits=10, decimal_places=7, widget=forms.HiddenInput())
    pio_outside_map_orp = forms.CharField(max_length=120, required=False, label="PIO — ORP z mapy")
    pio_outside_map_iczuj = forms.CharField(max_length=20, required=False, label="PIO — IČZÚJ z mapy")

    class Meta:
        model = NameSubjectProfile
        fields = ("is_municipality", "nitropodnikovy_subjekt")
        labels = {
            "is_municipality": "Jedná se o obec",
            "nitropodnikovy_subjekt": "Nitropodnikový subjekt",
        }
        help_texts = {
            "is_municipality": "Označí subjekt jako obec — používá se u obecních záznamů a související logiky v aplikaci.",
        }

    def _satellite_labels_help(self):
        self.fields["is_collection_yard"].label = "Lokalita sběrného dvora"
        self.fields["yard_allow_pruvodka"].label = "Povolit průvodku z dvora"
        self.fields["yard_allow_matrix"].label = "Povolit matici požadavků"
        self.fields["yard_svoz_dispatch_group"].label = "Skupina v plánu svozů"
        self.fields["system_generates_zpo"].label = "Generovat systémové ZPO k jízdám"
        self.fields["contact_phone"].label = "Telefon"
        self.fields["contact_note"].label = "Poznámka"
        self.fields["fulfillment_orp"].label = "ORP Adresa plnění (Obec s rozšířenou působností)"
        self.fields["fulfillment_iczuj"].label = "IČZÚJ (identifikační číslo základní územní jednotky)"
        self.fields["pio_officer_name"].label = "PIO — jméno odpovědné osoby"
        self.fields["pio_officer_phone"].label = "PIO — telefon osoby"
        self.fields["pio_officer_email"].label = "PIO — e-mail"
        self.fields["pio_waste_type"].label = "PIO — druh odpadu"
        self.fields["pio_suffix"].label = "PIO — koncovka"
        self.fields["pio_outside_map_orp"].label = "PIO — ORP z mapy"
        self.fields["pio_outside_map_iczuj"].label = "PIO — IČZÚJ z mapy"
        self.fields["is_collection_yard"].help_text = (
            "Zaškrtněte u subjektů sběrného dvora (matice požadavků, průvodky z dvora)."
        )
        self.fields["yard_allow_pruvodka"].help_text = 'Samostatně povolí založení průvodky z dvora (vstup „Nová jízda“).'
        self.fields["yard_allow_matrix"].help_text = 'Samostatně povolí matici požadavků na svoz (vstup „Požadavek na svoz“).'
        self.fields["yard_svoz_dispatch_group"].help_text = (
            "Krátký název pro seskupení řádků na obrazovce Plán svozů (volitelné)."
        )
        self.fields["system_generates_zpo"].help_text = (
            "Vypněte, pokud ZPO k jízdám nechcete generovat ze systému (podklady jinde nebo nejsou potřeba)."
        )
        self.fields["contact_note"].help_text = (
            "Interní poznámka ke kontaktu u provozovny (např. provozní doba, poznámka pro dispečink)."
        )

    def __init__(self, *args, **kwargs):
        actor_user = kwargs.pop("actor_user", None)
        super().__init__(*args, **kwargs)
        self._satellite_labels_help()
        self.fields["contact_phone"].required = False
        self.fields["contact_note"].required = False
        self.fields["nitropodnikovy_subjekt"].required = False
        self.fields["contact_phone"].widget.attrs.update(
            {
                "placeholder": "000 000 000",
                "inputmode": "tel",
                "autocomplete": "tel",
            }
        )
        self.fields["contact_note"].widget.attrs["maxlength"] = 200
        self.fields["fulfillment_orp"].required = False
        self.fields["fulfillment_iczuj"].required = False
        self.fields["yard_svoz_dispatch_group"].required = False
        self.fields["fulfillment_orp"].help_text = "Volitelné. Pokud vyplněno, zadejte kód ORP (číslice)."
        self.fields["fulfillment_iczuj"].help_text = "Volitelné. Pokud vyplněno, zadejte pouze číslice."
        pio_optional = (
            "pio_officer_name",
            "pio_officer_phone",
            "pio_officer_email",
            "pio_waste_type",
            "pio_suffix",
            "pio_outside_map_orp",
            "pio_outside_map_iczuj",
        )
        for fn in pio_optional:
            if fn in self.fields:
                self.fields[fn].required = False
        if "pio_waste_type" in self.fields:
            self.fields["pio_waste_type"].empty_label = "—"
        if "pio_suffix" in self.fields:
            self.fields["pio_suffix"].empty_label = "—"
        self.fields["pio_officer_phone"].widget.attrs.update(
            {
                "placeholder": "000 000 000",
                "inputmode": "tel",
                "autocomplete": "tel",
            }
        )
        self.fields["name_value"].help_text = (
            "Název fyzické nebo právnické osoby v číselníku subjektů. Musí být unikátní — duplicita není povolena."
        )
        self.fields["ico_value"].help_text = (
            "Identifikační číslo organizace (8 číslic) — bez vyplnění zde subjekt nejde vyhledat podle IČO "
            "na nové jízdě ani v seznamu F/P. Tlačítkem „Načíst z ARES“ lze doplnit název a adresu provozovny."
        )
        self.fields["facility_address_value"].help_text = (
            "Adresa provozovny subjektu; zobrazuje se v přehledech a používá se u napovídání adres."
        )
        self.fields["fulfillment_address_value"].help_text = (
            "Adresa plnění odpovědnosti (typicky sídlo). Formát: ulice, číslo popisné, město. "
            "Ze zadané adresy a souřadnic lze dopočítat ORP a IČZÚJ."
        )
        self._apply_actor_subject_permissions(actor_user)
        _attach_native_tooltips(self)
        if self.instance and self.instance.pk:
            self.fields["name_value"].initial = self.instance.name.value
            self.fields["ico_value"].initial = self.instance.ico.value if self.instance.ico else ""
            self.fields["facility_address_value"].initial = (
                self.instance.facility_address.value if self.instance.facility_address else ""
            )
            self.fields["fulfillment_address_value"].initial = (
                self.instance.fulfillment_address.value if self.instance.fulfillment_address else ""
            )
            self.fields["facility_latitude"].initial = self.instance.facility_latitude
            self.fields["facility_longitude"].initial = self.instance.facility_longitude
            self.fields["fulfillment_latitude"].initial = self.instance.fulfillment_latitude
            self.fields["fulfillment_longitude"].initial = self.instance.fulfillment_longitude
            self.fields["is_collection_yard"].initial = self.instance.is_collection_yard
            self.fields["yard_allow_pruvodka"].initial = self.instance.yard_allow_pruvodka
            self.fields["yard_allow_matrix"].initial = self.instance.yard_allow_matrix
            self.fields["yard_svoz_dispatch_group"].initial = self.instance.yard_svoz_dispatch_group
            self.fields["system_generates_zpo"].initial = self.instance.system_generates_zpo
            self.fields["contact_note"].initial = self.instance.contact_note
            self.fields["fulfillment_orp"].initial = self.instance.fulfillment_orp
            self.fields["fulfillment_iczuj"].initial = self.instance.fulfillment_iczuj
            if (self.instance.contact_phone or "").strip():
                self.initial["contact_phone"] = format_czech_contact_phone(self.instance.contact_phone)
            # Sekce PIO: neprefillovat z uloženého profilu (minulé PIO). Adresa provozovny jen přes zrcadlo v šabloně.

    def _apply_actor_subject_permissions(self, actor_user) -> None:
        if not actor_user or not getattr(actor_user, "is_authenticated", False):
            return
        # Superuživatel (role Admin) neomezený — nejde „vypnout“ přes uživatelský profil přístupu.
        if getattr(actor_user, "is_superuser", False):
            return
        profile = get_access_profile(actor_user)
        field_perm_map = {
            "is_municipality": bool(profile.can_toggle_subject_is_municipality),
            "is_collection_yard": bool(profile.can_toggle_subject_collection_yard),
            "yard_allow_pruvodka": bool(profile.can_toggle_subject_yard_allow_pruvodka),
            "yard_allow_matrix": bool(profile.can_toggle_subject_yard_allow_matrix),
            "yard_svoz_dispatch_group": bool(profile.can_toggle_subject_dispatch_group),
            "nitropodnikovy_subjekt": bool(profile.can_toggle_subject_nitropodnikovy),
            "system_generates_zpo": bool(profile.can_toggle_subject_system_generates_zpo),
        }
        for field_name, allowed in field_perm_map.items():
            if allowed:
                continue
            field = self.fields.get(field_name)
            if not field:
                continue
            field.disabled = True
            field.help_text = (
                (field.help_text + " " if field.help_text else "")
                + "Změna je vypnutá v oprávnění uživatele."
            )

    def clean_fulfillment_orp(self):
        value = normalize_czech_address((self.cleaned_data.get("fulfillment_orp") or "").strip())
        if value and not value.isdigit():
            raise forms.ValidationError("ORP musí obsahovat pouze číslice (kód ORP).")
        return value

    def clean_fulfillment_iczuj(self):
        value = (self.cleaned_data.get("fulfillment_iczuj") or "").strip()
        if value and not value.isdigit():
            raise forms.ValidationError("IČZÚJ může obsahovat pouze číslice.")
        return value

    def clean_ico_value(self):
        ico = (self.cleaned_data.get("ico_value") or "").strip()
        if not ico:
            return ""
        if not ico.isdigit() or len(ico) != 8:
            raise forms.ValidationError("IČO musí mít přesně 8 číslic.")
        return ico

    def clean_name_value(self):
        value = (self.cleaned_data.get("name_value") or "").strip()
        if not value:
            raise forms.ValidationError("Zadejte název F/P osoby.")
        name_obj = NameCatalog.objects.filter(value=value).first()
        if not name_obj:
            return value
        current_name_id = self.instance.name_id if self.instance and self.instance.pk else None
        if current_name_id and name_obj.pk == current_name_id:
            return value
        existing_profile = NameSubjectProfile.objects.filter(name=name_obj).only("id").first()
        if existing_profile:
            edit_url = reverse("catalogs:name_edit", args=[existing_profile.id])
            raise forms.ValidationError(
                format_html(
                    "Subjekt s tímto názvem už existuje (ID: {}). "
                    '<a href="{}">Otevřít existující záznam</a>.',
                    existing_profile.id,
                    edit_url,
                )
            )
        return value

    def clean_contact_phone(self):
        raw = (self.cleaned_data.get("contact_phone") or "").strip()
        if not raw:
            return ""
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) < 9:
            raise forms.ValidationError("Telefon musí mít alespoň 9 číslic (např. 000 000 000).")
        return format_czech_contact_phone(raw)

    def clean_pio_officer_phone(self):
        raw = (self.cleaned_data.get("pio_officer_phone") or "").strip()
        if not raw:
            return ""
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) < 9:
            raise forms.ValidationError("Telefon musí mít alespoň 9 číslic (např. 000 000 000).")
        return format_czech_contact_phone(raw)

    def clean_pio_outside_map_orp(self):
        value = normalize_czech_address((self.cleaned_data.get("pio_outside_map_orp") or "").strip())
        if value and not value.isdigit():
            raise forms.ValidationError("ORP musí obsahovat pouze číslice (kód ORP).")
        return value

    def clean_pio_outside_map_iczuj(self):
        value = (self.cleaned_data.get("pio_outside_map_iczuj") or "").strip()
        if value and not value.isdigit():
            raise forms.ValidationError("IČZÚJ může obsahovat pouze číslice.")
        return value

    def clean_fulfillment_address_value(self):
        value = normalize_fulfillment_address((self.cleaned_data.get("fulfillment_address_value") or "").strip())
        if not is_valid_fulfillment_address_strict(value):
            raise forms.ValidationError(
                "Adresa plnění musí být ve formátu 'Ulice, číslo popisné, město'."
            )
        return value

    def clean_facility_address_value(self):
        value = (self.cleaned_data.get("facility_address_value") or "").strip()
        return normalize_czech_address(value)

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        name = (cleaned.get("name_value") or "").strip()
        ico = (cleaned.get("ico_value") or "").strip()
        if name and not ico and name.isdigit() and len(name) == 8:
            cleaned["ico_value"] = name
            self.add_error(
                "name_value",
                "IČO patří do pole IČO výše. Zadejte název firmy (např. tlačítkem „Načíst z ARES“).",
            )
        return cleaned

    def save(self, commit=True):
        name_value = self.cleaned_data["name_value"].strip()
        ico_value = self.cleaned_data.get("ico_value", "").strip()
        facility_address_value = self.cleaned_data.get("facility_address_value", "").strip()
        fulfillment_address_value = self.cleaned_data.get("fulfillment_address_value", "").strip()

        profile = super().save(commit=False)
        profile.company_name = name_value
        name, _ = NameCatalog.objects.get_or_create(value=name_value)
        profile.name = name

        profile.ico = IcoCatalog.objects.get_or_create(value=ico_value)[0] if ico_value else None

        if commit:
            profile.save()
            self.save_m2m()
            profile.facility_address = (
                AddressCatalog.objects.get_or_create(value=facility_address_value)[0]
                if facility_address_value
                else None
            )
            profile.fulfillment_address = (
                AddressCatalog.objects.get_or_create(value=fulfillment_address_value)[0]
                if fulfillment_address_value
                else None
            )
            profile.facility_latitude = self.cleaned_data.get("facility_latitude") or None
            profile.facility_longitude = self.cleaned_data.get("facility_longitude") or None
            profile.fulfillment_latitude = self.cleaned_data.get("fulfillment_latitude") or None
            profile.fulfillment_longitude = self.cleaned_data.get("fulfillment_longitude") or None
            profile.fulfillment_orp = self.cleaned_data.get("fulfillment_orp") or ""
            profile.fulfillment_iczuj = self.cleaned_data.get("fulfillment_iczuj") or ""
            profile.is_collection_yard = bool(self.cleaned_data.get("is_collection_yard"))
            profile.yard_allow_pruvodka = bool(self.cleaned_data.get("yard_allow_pruvodka"))
            profile.yard_allow_matrix = bool(self.cleaned_data.get("yard_allow_matrix"))
            profile.yard_svoz_dispatch_group = (self.cleaned_data.get("yard_svoz_dispatch_group") or "").strip()
            profile.system_generates_zpo = bool(self.cleaned_data.get("system_generates_zpo"))
            profile.contact_phone = self.cleaned_data.get("contact_phone") or ""
            profile.contact_note = self.cleaned_data.get("contact_note") or ""
            clear_subject_pio_profile_fields(profile)
            save_related_satellites(profile)
        return profile
