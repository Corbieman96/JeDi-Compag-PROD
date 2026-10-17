from django.forms.models import BaseInlineFormSet

from catalogs.pruvodka_guide_field_order import field_key_sort_index


class OrderedActivityFieldRuleFormSet(BaseInlineFormSet):
    """
    Řádky pro zobrazení seřadí podle pořadí polí ve formuláři průvodky.

    Nikdy nesmíme měnit pořadí ``self.forms`` — Django bere prvních
    ``initial_form_count()`` formulářů jako existující záznamy v DB a zbytek jako
    extra řádky; prohození pořadí po validaci rozbije ukládání (nové řádky se
    neuloží, existující se špatně zařadí).
    """

    @property
    def ordered_forms(self):
        idx = field_key_sort_index()
        tail = len(idx) + 10

        def sort_key(form):
            raw = ""
            if form.is_bound:
                raw = form["field_key"].value() or ""
            elif form.initial.get("field_key"):
                raw = form.initial["field_key"]
            elif form.instance.pk:
                raw = form.instance.field_key
            pos = idx.get(str(raw), tail)
            return (pos, form.prefix or "")

        return sorted(self.forms, key=sort_key)
