"""
Pořadí klíčů polí evidence na průvodce — stejné jako v šabloně `waste_docs/form.html`.

Slouží pro řazení řádků v editaci činnosti a pro konzistentní pořadí v rozbalovací nabídce pravidel.
"""

from __future__ import annotations

from catalogs.models import ActivityFieldKey

# Pořadí odpovídá vizuálnímu toku formuláře nové průvodky (řidič → vozidlo → kontejnery → …).
PRUVODKA_GUIDE_FIELD_KEYS: tuple[str, ...] = (
    ActivityFieldKey.DRIVER,
    ActivityFieldKey.VEHICLE_RZ,
    ActivityFieldKey.CONTAINER_1,
    ActivityFieldKey.CONTAINER_2,
    ActivityFieldKey.CONTACT_NOTE,
    ActivityFieldKey.NAME,
    ActivityFieldKey.FULFILLMENT_ADDRESS,
    ActivityFieldKey.CONTACT_PHONE,
    ActivityFieldKey.CONTRACT_NUMBER,
    ActivityFieldKey.WASTE_TYPE,
    ActivityFieldKey.SUFFIX,
    ActivityFieldKey.SND_CISLO,
    ActivityFieldKey.ZPO,
    ActivityFieldKey.PIO,
)


def field_key_sort_index() -> dict[str, int]:
    return {k: i for i, k in enumerate(PRUVODKA_GUIDE_FIELD_KEYS)}


def ordered_activity_field_key_choices():
    labels = dict(ActivityFieldKey.choices)
    return [(k, labels[k]) for k in PRUVODKA_GUIDE_FIELD_KEYS]
