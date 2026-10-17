"""Výpočet zobrazeného stavu skupiny průvodek (jedna jízda: datum + vozidlo)."""


def ride_group_count_meta(status: str, n: int) -> str:
    """
    Krátký text počtu pro dashboard jízd: u „Založeno“ jde o jízdu (záznam), ne o hotovou průvodku.
    Jinak zůstává zkratka „prův.“ jako počet záznamů ve skupině.
    """
    if status == "Založeno":
        if 11 <= (n % 100) <= 14:
            word = "jízd"
        elif n % 10 == 1:
            word = "jízda"
        elif 2 <= (n % 10) <= 4:
            word = "jízdy"
        else:
            word = "jízd"
        return f"{n} {word}"
    return f"{n} prův."


def ride_group_status_label(items: list) -> str:
    if not items:
        return "—"
    if any(getattr(r, "follow_up_open", False) for r in items):
        return "Čeká návaznost"
    has_file = [bool(r.generated_file) for r in items]
    if all(has_file):
        return "Vygenerováno"
    if not any(has_file):
        # Žádná průvodka ve skupině nemá vygenerovaný Excel — vždy „Založeno“ (i u činností bez evidence v Excelu).
        return "Založeno"
    return "Smíšeno"
