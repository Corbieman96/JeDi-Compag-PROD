"""Slovník a pravidla pro AI prompt — optimalizace pořadí zastávek jízdy."""

from __future__ import annotations

AI_TASK_LINES = [
    "Úkol: Navrhni optimální pořadí zastávek pro jednu trasu auta v systému JeDiS.",
    "Cíl: z navržených průvodek sestavit logické pořadí jízdy tak, aby výstupem byl "
    "pouze seznam pk průvodek v pořadí trasy.",
]

GLOSSARY_LINES = [
    "Důležité pojmy:",
    "- pk = ID průvodky; používá se pro výstup a řazení.",
    "- SND = evidenční číslo dokumentu; při řazení se nikdy nemění.",
    "- Subjekt = zákazník, sběrný dvůr, skládka, kompostárna nebo depo.",
    "- Činnost určuje směr a smysl zastávky.",
    "- Přistavení / Přistavit: auto veze prázdný kontejner na místo, složí ho a odjede. "
    "Má být provedeno dříve, aby mohl být kontejner následně naložen.",
    "- Stažení / Stáhnout: auto se vrací pro již naložený nebo připravený kontejner "
    "(druhá návštěva tentýž den; mezitím může auto jezdit jinde).",
    "- Přistavit a Stáhnout: kombinovaná zakázka — respektuj čas zákazníka z poznámky "
    "a koncovku odpadu.",
    "- Výměna: na místě se odveze plný kontejner a složí prázdný; trvá déle než běžné přistavení.",
    "- Jiná činnost: běžná pracovní zastávka — řaď podle místa, koncovky a návaznosti.",
    "- Nic / Nic u subjektu COMPAG MLADÁ BOLESLAV s.r.o. = výchozí bod / depo / technická "
    "průvodka trasy → má být na začátku, pokud je v seznamu.",
    "- Kontejner: číslo VOK; u výměny mohou být 2 čísla.",
    "- Koncovka: kam se veze odpad (skládka, kompostárna, ROIN, depo…).",
    "- Poznámka: časy (v 9h, kolem 12h), preference zákazníka, ručaři, vjezd…",
    "- Odhad min: odhad délky zastávky auta na místě (ne jízda mezi body).",
    "- Návaznost: vazba přistavení → stažení (sloupec návaznost).",
]

ROUTING_PRIORITY_LINES = [
    "Pravidla řazení:",
    "1. Nikdy nevymýšlej pk, které není ve vstupních datech.",
    "2. Do výstupu vrať vždy všechna pk ze vstupu — patří do dané trasy.",
    "3. SND nikdy nepřečíslovávej ani neměň.",
    "4. COMPAG MLADÁ BOLESLAV s.r.o. s odpadem/koncovkou Nic → první (depo / začátek trasy).",
    "5. Přistavení zařazuj co nejdříve, aby zákazník nebo ručaři mohli kontejner plnit.",
    "6. Poznámka „v 9h“ = pevný čas — zastávka musí být v pořadí tak, aby šlo čas splnit.",
    "7. „kolem 12h“ = preferovaný čas — před ní lze jiné zastávky, pokud to logisticky dává smysl.",
    "8. Stejná adresa / lokalita → za sebou (auto se nemusí vracet).",
    "9. Stejná koncovka nebo stejný směr → seskupit, minimalizovat zbytečné kilometry.",
    "10. Výměny a svozy na koncovku: zákazník → koncovka → další logická zastávka.",
    "11. Zohledni: vzdálenost, směr jízdy, činnost, odhad min, poznámky, "
    "nutnost nejdříve přistavit a pak stahovat, návaznost na skládku/kompostárnu/ROIN/depo.",
    "12. Samotné přistavení (bez stažení v téže zastávce) může být brzy v trase — "
    "auto složí kontejner a pokračuje.",
    "13. Dvě průvodky na stejné adrese → bezprostředně za sebe.",
    "14. Přistavení vždy před stažením u stejného místa; mezi párem lze vložit jiné zastávky.",
]

PROMPT_EXAMPLE_LINES = [
    "Příklad (logika, ne kopírovat pk):",
    "#813 COMPAG … | Nic | Nic  →  první (depo)",
    "#788 … | Přistavit | …  →  brzy (ať se může plnit)",
    "#791 … | Přistavit a Stáhnout | … | poznámka: v 9h  →  včas",
    "#790 … | Výměna | …",
    "#806, #807 … | stejná adresa  →  za sebou",
    "Očekávaný výstup pro tento příklad: 813, 788, 791, 790, 806, 807 (jen pk, jedno na řádek).",
]

OUTPUT_FORMAT_LINES = [
    "Výstupní formát (povinný):",
    "- Pouze seznam pk, jedno pk na řádek.",
    "- Žádné vysvětlení, žádné SND, žádné názvy subjektů, žádné odrážky.",
    "- Příklad:",
    "813",
    "788",
    "791",
]


def _activity_label_lower(name: str) -> str:
    return (name or "").strip().lower()


def describe_activity_label(name: str) -> str | None:
    """Krátké vysvětlení činnosti pro AI podle názvu z číselníku."""
    label = _activity_label_lower(name)
    if not label:
        return None
    norm = label.replace("í", "i").replace("ě", "e").replace("ř", "r").replace("š", "s")
    if "vymena" in norm or "výměna" in label:
        return f"{name.strip()} = výměna VOK na místě (plný pryč + prázdný na místo)"
    if "pristav" in norm and any(t in norm for t in ("stahn", "staz")):
        return f"{name.strip()} = přistavit a stáhnout — kombinovaná zakázka, respektuj čas v poznámce"
    if any(t in label for t in ("stažení", "stazeni", "stáhnout", "stahnout")) or (
        "stahn" in norm or "staz" in norm
    ):
        return f"{name.strip()} = stažení — druhá návštěva / odvoz kontejneru"
    if "pristav" in norm:
        return f"{name.strip()} = přistavit — složit prázdný kontejner a odjet"
    if "svoz" in label:
        return f"{name.strip()} = svoz odpadu z místa do koncovky"
    if "jina" in norm or "jiná" in label:
        return f"{name.strip()} = jiná činnost — běžná zastávka"
    if "odvoz" in label:
        return f"{name.strip()} = odvoz"
    return None


def build_activity_summary_lines(activity_names: list[str]) -> list[str]:
    """Řádky s vysvětlením činností vyskytujících se v jízdě."""
    seen: set[str] = set()
    descriptions: list[str] = []
    for raw in activity_names:
        name = (raw or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        desc = describe_activity_label(name)
        if desc:
            descriptions.append(f"- {desc}")
    if not descriptions:
        return []
    return ["V této jízdě se vyskytují činnosti:", *descriptions]
