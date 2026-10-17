"""Pořadí řádků párů odpad–koncovka u subjektu (matice svozu, tabulka F/P)."""

from __future__ import annotations

from django.forms import BaseInlineFormSet

from catalogs.models import NameSubjectWasteSuffixPair


def normalize_waste_suffix_pair_sort_order(formset: BaseInlineFormSet) -> None:
    """Po uložení formsetu přepíše sort_order na 0..n podle hodnot z formuláře (DnD mění skrytá pole)."""
    rows: list[tuple[int, int, int]] = []
    for i, form in enumerate(formset.forms):
        if not hasattr(form, "cleaned_data") or not form.cleaned_data:
            continue
        if form.cleaned_data.get("DELETE"):
            continue
        inst = form.instance
        if not inst.pk:
            continue
        try:
            so = int(form.cleaned_data.get("sort_order", 0))
        except (TypeError, ValueError):
            so = 0
        rows.append((so, i, inst.pk))
    rows.sort(key=lambda x: (x[0], x[1]))
    for idx, (_, _, pk) in enumerate(rows):
        NameSubjectWasteSuffixPair.objects.filter(pk=pk).update(sort_order=idx)
