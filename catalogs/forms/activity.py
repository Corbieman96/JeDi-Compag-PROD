from django import forms
from django.forms import inlineformset_factory

from catalogs.forms.activity_field_rules import OrderedActivityFieldRuleFormSet
from catalogs.models import ActivityCatalog, ActivityFieldKey, ActivityFieldMode, ActivityFieldRule, VehicleKindCatalog
from catalogs.pruvodka_guide_field_order import ordered_activity_field_key_choices
from waste_docs.activity_fields import effective_container_slot_count


class ActivityCatalogForm(forms.ModelForm):
    mobile_container_slots = forms.TypedChoiceField(
        coerce=int,
        choices=(
            (
                1,
                "Jeden kontejner — v mobilní průvodce jen číslo kontejneru (1); pole „(2)“ bude skryté",
            ),
            (
                2,
                "Dva kontejnery — obě pole (např. přistavení + stažený / výměna)",
            ),
        ),
        widget=forms.RadioSelect,
        label="Kontejnery v průvodce",
        help_text="řídí režim polí v aplikaci v terénu; podrobné režimy (povinné/volné) lze doladit v tabulce níže u řádků „Číslo kontejneru (1)“ a „(2)“.",
        initial=1,
    )

    class Meta:
        model = ActivityCatalog
        fields = (
            "name",
            "default_service_minutes",
            "vehicle_kinds",
            "follow_up_activities",
            "follow_up_terminal_activities",
            "follow_up_symbol_parent",
            "follow_up_symbol_child",
            "evidence_without_excel",
            "require_nitropodnikovy_subjekt",
        )
        labels = {
            "name": "Druh činnosti",
            "default_service_minutes": "Výchozí délka zastávky (min)",
            "vehicle_kinds": "Číselník druhů vozidel",
            "follow_up_activities": "Hlídat dokončení činnosti (návaznost)",
            "follow_up_terminal_activities": "Uzavírají návaznost",
            "follow_up_symbol_parent": "Symbol návaznosti k předchozí jízdě",
            "follow_up_symbol_child": "Symbol k navazujícím jízdám",
            "evidence_without_excel": "Stačí evidence v databázi (bez Excelu)",
            "require_nitropodnikovy_subjekt": "Vnitropodnikový subjekt",
        }
        widgets = {
            "default_service_minutes": forms.NumberInput(attrs={"min": 1, "max": 999, "style": "max-width:6rem;"}),
            "vehicle_kinds": forms.SelectMultiple(attrs={"size": 10}),
            "follow_up_activities": forms.SelectMultiple(attrs={"size": 10}),
            "follow_up_terminal_activities": forms.SelectMultiple(attrs={"size": 6}),
            "follow_up_symbol_parent": forms.TextInput(attrs={"maxlength": 8, "style": "max-width:12rem;"}),
            "follow_up_symbol_child": forms.TextInput(attrs={"maxlength": 8, "style": "max-width:12rem;"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from catalogs.services.vehicle_kind_display import bind_vehicle_kind_select_labels

        self.fields["vehicle_kinds"].queryset = VehicleKindCatalog.objects.order_by("name")
        bind_vehicle_kind_select_labels(self, "vehicle_kinds")
        fu_qs = ActivityCatalog.objects.order_by("name")
        if self.instance.pk:
            fu_qs = fu_qs.exclude(pk=self.instance.pk)
        self.fields["follow_up_activities"].queryset = fu_qs
        self.fields["follow_up_activities"].required = False
        self.fields["follow_up_terminal_activities"].queryset = fu_qs
        self.fields["follow_up_terminal_activities"].required = False
        if self.instance.pk and not self.instance.follow_up_activities.exists() and self.instance.follow_up_activity_id:
            self.initial["follow_up_activities"] = [self.instance.follow_up_activity_id]
        if self.instance.pk:
            self.fields["mobile_container_slots"].initial = effective_container_slot_count(self.instance.pk)
        self.fields["evidence_without_excel"].required = False
        self.fields["require_nitropodnikovy_subjekt"].required = False
        self.fields["default_service_minutes"].required = False
        self.fields["default_service_minutes"].help_text = (
            "Odhad času auta na místě pro AI prompt řazení trasy (např. přistavení 12, stažení 18, výměna 35)."
        )
        self.order_fields(
            (
                "name",
                "default_service_minutes",
                "vehicle_kinds",
                "mobile_container_slots",
                "follow_up_activities",
                "follow_up_terminal_activities",
                "follow_up_symbol_parent",
                "follow_up_symbol_child",
                "evidence_without_excel",
                "require_nitropodnikovy_subjekt",
            )
        )

    def clean(self):
        cleaned = super().clean()
        selected = list(cleaned.get("follow_up_activities") or [])
        terminals = list(cleaned.get("follow_up_terminal_activities") or [])
        selected_ids = {act.pk for act in selected}
        for act in terminals:
            if act.pk not in selected_ids:
                self.add_error(
                    "follow_up_terminal_activities",
                    "Uzavírající činnosti musí být vybrány i mezi návaznostmi výše.",
                )
                break
        if len(selected) == 1 and not terminals:
            cleaned["follow_up_terminal_activities"] = selected
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=commit)
        selected = list(self.cleaned_data.get("follow_up_activities") or [])
        primary = selected[0] if selected else None
        primary_id = primary.pk if primary else None
        if instance.follow_up_activity_id != primary_id:
            instance.follow_up_activity = primary
            if commit:
                instance.save(update_fields=["follow_up_activity"])
        return instance


class ActivityFieldRuleForm(forms.ModelForm):
    class Meta:
        model = ActivityFieldRule
        fields = ("field_key", "mode")
        labels = {
            "field_key": "Položka evidence",
            "mode": "Režim",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["field_key"].choices = [("", "---------")] + ordered_activity_field_key_choices()

    def clean(self):
        cleaned = super().clean()
        fk = cleaned.get("field_key")
        mode = cleaned.get("mode")
        if (
            fk
            and mode == ActivityFieldMode.OFF
            and fk in (ActivityFieldKey.NAME, ActivityFieldKey.WASTE_TYPE)
        ):
            self.add_error(
                "mode",
                "U položek „Subjekt“ a „Druh odpadu“ nelze zvolit režim skryté — průvodka je na nich závislá.",
            )
        return cleaned


ActivityFieldRuleFormSet = inlineformset_factory(
    ActivityCatalog,
    ActivityFieldRule,
    form=ActivityFieldRuleForm,
    formset=OrderedActivityFieldRuleFormSet,
    extra=1,
    can_delete=True,
    min_num=0,
)
