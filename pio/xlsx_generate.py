"""
Generování předvyplněného Excelu PIO (placeholdery {{PIO_*}} ve šabloně nebo jednoduchý výpis).
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
import unicodedata

from django.conf import settings
from django.http import QueryDict
from django.utils import timezone

from catalogs.models import NameSubjectProfile, NameSubjectWasteSuffixPair, SuffixCatalog, WasteTypeCatalog
from catalogs.services import normalize_czech_address
from catalogs.services.fulfillment_address import normalize_fulfillment_address
from catalogs.waste_catalog_code import normalize_waste_catalog_code

try:
    from openpyxl import Workbook, load_workbook
except ModuleNotFoundError:  # pragma: no cover
    Workbook = None  # type: ignore[misc, assignment]
    load_workbook = None  # type: ignore[misc, assignment]

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_TEMPLATE_PATH = PACKAGE_DIR / "static" / "pio" / "pio_template.xlsx"


def format_pio_koncovka_placeholder(suffix: SuffixCatalog | None) -> str:
    """Název koncovky pro PIO; s IČZ z profilu koncovky ve tvaru ``IČZ: {icz} {název}``."""
    label = (suffix.value if suffix else "") or ""
    if not label:
        return ""
    icz = ""
    if suffix and suffix.pk:
        profile = getattr(suffix, "site_profile", None)
        if profile is not None:
            icz = (profile.icz or "").strip()
    if icz:
        return f"IČZ: {icz} {label}"
    return label


def pio_placeholder_map(subject: NameSubjectProfile, pair: NameSubjectWasteSuffixPair) -> dict[str, str]:
    """Hodnoty pro nahrazení tokenů {{PIO_…}} v šabloně .xlsx."""
    ico = (subject.ico.value if subject.ico_id else "") or ""
    name_fp = (subject.name.value if subject.name_id else "") or ""
    ful = (subject.fulfillment_address.value if subject.fulfillment_address_id else "") or ""
    fac = (subject.facility_address.value if subject.facility_address_id else "") or ""
    orp = (subject.fulfillment_orp or "").strip()
    iczuj = (subject.fulfillment_iczuj or "").strip()
    wt = pair.waste_type
    code_raw = wt.code if wt else ""
    code_disp = normalize_waste_catalog_code(code_raw) if wt else ""
    waste_name = (wt.value if wt else "") or ""
    waste_cat = (wt.category if wt else "") or ""
    suffix = format_pio_koncovka_placeholder(pair.suffix if pair.suffix_id else None)
    contract = (pair.contract_number or "").strip()
    today = timezone.localdate().strftime("%d.%m.%Y")
    company = (subject.company_name or "").strip()

    return {
        "{{PIO_COMPANY}}": company,
        "{{PIO_NAME_FP}}": name_fp,
        "{{PIO_ICO}}": ico,
        "{{PIO_FULFILLMENT_ADDRESS}}": ful,
        "{{PIO_FACILITY_ADDRESS}}": fac,
        "{{PIO_ORP}}": orp,
        "{{PIO_ICZUJ}}": iczuj,
        "{{PIO_WASTE_CODE}}": code_disp or (code_raw or ""),
        "{{PIO_WASTE_CODE_RAW}}": code_raw or "",
        "{{PIO_WASTE_NAME}}": waste_name,
        "{{PIO_WASTE_CATEGORY}}": waste_cat,
        "{{PIO_SUFFIX}}": suffix,
        "{{PIO_CONTRACT}}": contract,
        "{{PIO_DATE}}": today,
    }


def _replace_in_workbook(wb, values: dict[str, str]) -> None:
    for sheet in wb.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and "{{" in cell.value and "}}" in cell.value:
                    out = cell.value
                    for token, replacement in values.items():
                        out = out.replace(token, replacement)
                    cell.value = out


def replace_placeholder_tokens_in_workbook(wb, values: dict[str, str]) -> None:
    """Veřejný alias nad :func:`_replace_in_workbook` (sdílené i uživatelské šabloně PIO)."""
    _replace_in_workbook(wb, values)


def _fallback_workbook(subject: NameSubjectProfile, pair: NameSubjectWasteSuffixPair):
    wb = Workbook()
    ws = wb.active
    ws.title = "PIO"
    ws["A1"] = "Prvotní informace o odpadu — předvyplnění (JeDiS)"
    ws["A2"] = "Doplňte údaje podle vaší legislativní šablony; tento list slouží jako export dat z číselníku."

    values = pio_placeholder_map(subject, pair)
    rows = [
        ("Obchodní firma / název subjektu", values["{{PIO_COMPANY}}"]),
        ("Název F/P osoby (katalog)", values["{{PIO_NAME_FP}}"]),
        ("IČO", values["{{PIO_ICO}}"]),
        ("Adresa plnění", values["{{PIO_FULFILLMENT_ADDRESS}}"]),
        ("Adresa provozovny", values["{{PIO_FACILITY_ADDRESS}}"]),
        ("ORP (adresa plnění)", values["{{PIO_ORP}}"]),
        ("IČZÚJ (adresa plnění)", values["{{PIO_ICZUJ}}"]),
        ("Kód odpadu", values["{{PIO_WASTE_CODE}}"]),
        ("Název druhu odpadu", values["{{PIO_WASTE_NAME}}"]),
        ("Kategorie odpadu (katalog)", values["{{PIO_WASTE_CATEGORY}}"]),
        ("Koncovka", values["{{PIO_SUFFIX}}"]),
        ("Číslo smlouvy (pár)", values["{{PIO_CONTRACT}}"]),
        ("Datum vygenerování", values["{{PIO_DATE}}"]),
    ]
    start = 4
    for i, (label, val) in enumerate(rows):
        ws.cell(row=start + i, column=1, value=label)
        ws.cell(row=start + i, column=2, value=val)
    ws.column_dimensions["A"].width = 36
    ws.column_dimensions["B"].width = 52
    return wb


def template_path_for_pio() -> Path | None:
    configured = getattr(settings, "PIO_XLSX_TEMPLATE", None)
    if configured:
        p = Path(configured)
        if p.is_file():
            return p
    if DEFAULT_TEMPLATE_PATH.is_file():
        return DEFAULT_TEMPLATE_PATH
    return None


def generate_pio_xlsx_bytes(subject: NameSubjectProfile, pair: NameSubjectWasteSuffixPair) -> bytes:
    if Workbook is None or load_workbook is None:
        raise RuntimeError("Knihovna openpyxl není nainstalovaná.")

    values = pio_placeholder_map(subject, pair)
    tpl = template_path_for_pio()
    if tpl:
        wb = load_workbook(tpl)
        _replace_in_workbook(wb, values)
    else:
        wb = _fallback_workbook(subject, pair)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def template_path_for_user_pio() -> Path | None:
    """Excel šablona pro generování PIO z profilu subjektu: ``settings.PIO_USER_XLSX_TEMPLATE`` (výchozí ``BASE_DIR / 'PIO.xlsx'``)."""
    path = getattr(settings, "PIO_USER_XLSX_TEMPLATE", None)
    if path is None:
        base = getattr(settings, "BASE_DIR", None)
        path = Path(base) / "PIO.xlsx" if base else None
    else:
        path = Path(path)
    return path if path and path.is_file() else None


def _pio_waste_suffix_pk(raw) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        v = int(str(raw).strip())
        return v if v > 0 else None
    except ValueError:
        return None


def resolve_user_pio_waste_and_suffix_explicit(
    subject: NameSubjectProfile,
    wt: WasteTypeCatalog | None,
    suf: SuffixCatalog | None,
):
    """
    Společná logika: vybraný odpad + koncovka; případ doplnění z páru uloženého na profilu.
    """
    if wt and suf:
        return wt, suf

    qs = subject.waste_suffix_pairs.select_related("waste_type", "suffix").order_by("sort_order", "id")

    if wt is None and suf is None:
        pair = qs.first()
        return (pair.waste_type, pair.suffix) if pair else (None, None)

    if wt is not None and suf is None:
        pair = qs.filter(waste_type_id=wt.pk).first() or qs.first()
        return wt, (pair.suffix if pair else None)

    pair = qs.filter(suffix_id=suf.pk).first() or qs.first()
    return (pair.waste_type if pair else None), suf


def resolve_user_pio_waste_and_suffix(subject: NameSubjectProfile):
    """
    Druh odpadu a koncovka pro profilové PIO ve šabloně z řádků „Povolené odpady a koncovky“
    (první řádek podle ``sort_order``, ``id``). Pole PIO na profilu se neukládají.
    """
    return resolve_user_pio_waste_and_suffix_explicit(subject, None, None)


def resolve_user_pio_waste_and_suffix_from_live_post(subject: NameSubjectProfile, post: QueryDict):
    """
    Jako :func:`resolve_user_pio_waste_and_suffix`, ale výchozí výběr odpadu/koncovky z aktuálního POST
    (neuložený stav formuláře).
    """
    wt_id = _pio_waste_suffix_pk(post.get("pio_waste_type"))
    suf_id = _pio_waste_suffix_pk(post.get("pio_suffix"))
    wt = WasteTypeCatalog.objects.filter(pk=wt_id).first() if wt_id else None
    suf = SuffixCatalog.objects.filter(pk=suf_id).first() if suf_id else None
    return resolve_user_pio_waste_and_suffix_explicit(subject, wt, suf)


def _filename_segment_ascii_no_diacritics(text: str) -> str:
    """Převod na znaky bez diakritiky (vhodné pro název souboru v OS / e-mailu)."""
    if not text:
        return text
    nfd = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def _filename_segment_safe_piece(text: str, *, default: str, max_len: int) -> str:
    """Meziny jako _, bez znaků zakázaných ve Windows názvech; diakritiku odebere."""
    s = (text or "").strip()
    s = _filename_segment_ascii_no_diacritics(s)
    if not s:
        return default
    for bad in '<>:"/\\|?*':
        s = s.replace(bad, "")
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_") or default
    return s[:max_len]


def _filename_segment_waste_code_for_download(wt) -> str:
    if not wt or not ((wt.code or "").strip()):
        return "odpad"
    raw = normalize_waste_catalog_code(wt.code).strip().replace(" ", "_").replace("*", "hvezdicka")
    return _filename_segment_safe_piece(raw, default="odpad", max_len=40)


def _user_pio_download_stem(wt, suf, fp_person_name: str) -> str:
    """Část názvu bez ``.xlsx``: ``kód_odpadu_Jméno_F_P_osoby_koncovka``."""
    code_part = _filename_segment_waste_code_for_download(wt)
    name_part = _filename_segment_safe_piece(fp_person_name, default="subjekt", max_len=80)
    suf_txt = ((suf.value if suf else "") or "").strip()
    suf_part = _filename_segment_safe_piece(suf_txt, default="koncovka", max_len=60)
    base = f"{code_part}_{name_part}_{suf_part}"
    if len(base) > 180:
        base = base[:180].rstrip("_")
    return base


def _pio_download_filename_fp_person_segment(
    subject: NameSubjectProfile, post: QueryDict | None = None
) -> str:
    """
    Prostřední část názvu stahovaného souboru PIO: ``kód_F_P_osoby_koncovka``.

    Pouze název F/P osoby z číselníku (`name_value` při POST / uložený vztah).

    Obchodní firma (``company_name``) se do názvu souboru nedává — podle konvence kód_odpadu_F_P_osoba_koncovka.
    """
    if post is not None:
        v = (post.get("name_value") or "").strip()
        if v:
            return v
    return (subject.name.value if subject.name_id else "") or ""


def _missing_user_pio_export_minimum_labels(
    *,
    officer_name: str,
    officer_phone: str,
    officer_email: str,
    has_waste_type: bool,
    has_suffix: bool,
) -> list[str]:
    missing: list[str] = []
    if not (officer_name or "").strip():
        missing.append("PIO — jméno odpovědné osoby")
    digits = "".join(ch for ch in (officer_phone or "") if ch.isdigit())
    if len(digits) < 9:
        missing.append("PIO — telefon osoby")
    em = (officer_email or "").strip()
    if not em or "@" not in em:
        missing.append("PIO — e-mail")
    if not has_waste_type:
        missing.append("PIO — druh odpadu")
    if not has_suffix:
        missing.append("PIO — koncovka")
    return missing


def _raise_if_user_pio_export_minimum_missing_subject(subject: NameSubjectProfile) -> None:
    missing = _missing_user_pio_export_minimum_labels(
        officer_name=subject.pio_officer_name or "",
        officer_phone=subject.pio_officer_phone or "",
        officer_email=subject.pio_officer_email or "",
        has_waste_type=bool(subject.pio_waste_type_id),
        has_suffix=bool(subject.pio_suffix_id),
    )
    if missing:
        raise RuntimeError(
            "Nelze vygenerovat PIO — v sekci PIO je nutné vyplnit: "
            + "; ".join(missing)
            + "."
        )


def _raise_if_user_pio_officer_contact_minimum(subject: NameSubjectProfile) -> None:
    """Pouze kontakt PIO na profilu; druh odpadu a koncovka berou z kontextu páru."""
    missing = _missing_user_pio_export_minimum_labels(
        officer_name=subject.pio_officer_name or "",
        officer_phone=subject.pio_officer_phone or "",
        officer_email=subject.pio_officer_email or "",
        has_waste_type=True,
        has_suffix=True,
    )
    if missing:
        raise RuntimeError(
            "Nelze vygenerovat PIO — v sekci PIO je nutné vyplnit: "
            + "; ".join(missing)
            + "."
        )


def _raise_if_user_pio_export_minimum_missing_post(post: QueryDict, subject: NameSubjectProfile) -> None:
    wt, suf = resolve_user_pio_waste_and_suffix_from_live_post(subject, post)
    missing = _missing_user_pio_export_minimum_labels(
        officer_name=post.get("pio_officer_name") or "",
        officer_phone=post.get("pio_officer_phone") or "",
        officer_email=post.get("pio_officer_email") or "",
        has_waste_type=bool(wt),
        has_suffix=bool(suf),
    )
    if missing:
        raise RuntimeError(
            "Nelze vygenerovat PIO — v sekci PIO je nutné vyplnit: "
            + "; ".join(missing)
            + "."
        )


def _build_user_pio_token_values(
    *,
    ico: str,
    company: str,
    fac: str,
    ful: str,
    orp_ful: str,
    iczuj_ful: str,
    map_orp: str,
    map_iczuj: str,
    wt,
    suf,
    officer: str,
    phone: str,
    email: str,
) -> dict[str, str]:
    # Pole z mapy „mimo provozovnu“. Jsou-li obě prázdná, tokeny {{iczujfirmy}} a {{orp}} zůstanou prázdné (bez pádu na ORP/IČZÚJ z adresy plnění).
    map_orp_clean = (map_orp or "").strip()
    map_iczuj_clean = (map_iczuj or "").strip()
    if not map_orp_clean and not map_iczuj_clean:
        token_iczujfirmy = ""
        token_orp_special = ""
    else:
        token_iczujfirmy = map_orp_clean or orp_ful
        token_orp_special = map_iczuj_clean or iczuj_ful

    code_raw = ""
    code_disp = ""
    waste_name = ""
    waste_cat = ""
    desc_fo = ""
    desc_po = ""
    if wt:
        code_raw = (wt.code or "") or ""
        code_disp = normalize_waste_catalog_code(code_raw) if code_raw else ""
        waste_name = (wt.value or "") or ""
        waste_cat = (wt.category or "") or ""
        desc_fo = (wt.description_fo or "") or ""
        desc_po = (wt.description_po or "") or ""

    has_ico = bool(ico and len(ico) == 8)
    desc_fo_po = desc_po if has_ico else desc_fo

    suffix = format_pio_koncovka_placeholder(suf)
    datum_vyplneni = timezone.localdate().strftime("%d.%m.%Y")

    return {
        "{{datumvyplněni}}": datum_vyplneni,
        "{{koncovka}}": suffix,
        "{{menofirmy}}": company,
        "{{adresafirmy}}": fac,
        "{{ico}}": ico,
        "{{adresakde}}": ful,
        "{{orpfirmy}}": orp_ful,
        "{{iczuj}}": iczuj_ful,
        "{{iczujfirmy}}": token_iczujfirmy,
        "{{orp}}": token_orp_special,
        "{{prijmeniosoby}}": officer,
        "{{adresaiosoby}}": fac,
        "{{telefonosoby}}": phone,
        "{{email}}": email,
        "{{odpad}}": code_disp or code_raw,
        "{{druh}}": waste_cat,
        "{{nazevodpadu}}": waste_name,
        "{{odpad-vzik-pra-fyzicka}}": desc_fo_po,
    }


def user_pio_placeholder_map(
    subject: NameSubjectProfile,
    *,
    waste_suffix_pair: NameSubjectWasteSuffixPair | None = None,
) -> dict[str, str]:
    """
    Tokeny pro uživatelskou šablonu PIO (např. ``PIO.xlsx``).

    Vrstvení:

    - **Primárně sekce PIO** (`pio_officer_*`, druh/koncovka aj.). Pro ``{{iczujfirmy}}`` / ``{{orp}}``: jsou-li prázdná obě pole z mapy „mimo provozovnu“, oba tokeny zůstanou prázdné (nepřebírá se adresu plnění); jinak mapa ± doplnění z adresy plnění.
    - **Poté společná pole profilu** (sekce Identifikace / Adresy nad PIO ve formuláři):
      IČO, název firmy, text adres provozovny a plnění, ORP/IČZÚJ u adresy plnění.
      Adresa provozovny je jedna hodnota v číselníku adres — vyplnit lze v Adresách i v zrcadle PIO.

    Pokud je předán ``waste_suffix_pair``, hodnoty ``{{odpad}}``, ``{{koncovka}}`` a související berou z tohoto páru (stejná šablona jako při výběru páru na archivu PIO).
    """
    ico = (subject.ico.value if subject.ico_id else "") or ""
    company = (subject.company_name or "").strip()
    fac = (subject.facility_address.value if subject.facility_address_id else "") or ""
    ful = (subject.fulfillment_address.value if subject.fulfillment_address_id else "") or ""
    orp_ful = (subject.fulfillment_orp or "").strip()
    iczuj_ful = (subject.fulfillment_iczuj or "").strip()
    map_orp = (subject.pio_outside_map_orp or "").strip()
    map_iczuj = (subject.pio_outside_map_iczuj or "").strip()
    if waste_suffix_pair is not None:
        wt, suf = waste_suffix_pair.waste_type, waste_suffix_pair.suffix
    else:
        wt, suf = resolve_user_pio_waste_and_suffix(subject)
    officer = (subject.pio_officer_name or "").strip()
    phone = (subject.pio_officer_phone or "").strip()
    email = (subject.pio_officer_email or "").strip()
    return _build_user_pio_token_values(
        ico=ico,
        company=company,
        fac=fac,
        ful=ful,
        orp_ful=orp_ful,
        iczuj_ful=iczuj_ful,
        map_orp=map_orp,
        map_iczuj=map_iczuj,
        wt=wt,
        suf=suf,
        officer=officer,
        phone=phone,
        email=email,
    )


def user_pio_placeholder_map_from_live_post(subject: NameSubjectProfile, post: QueryDict) -> dict[str, str]:
    """Placeholdery z aktuálního stavu polí formuláře (POST), i když nejsou uložena v databázi."""
    fac = normalize_czech_address((post.get("facility_address_value") or "").strip())
    ful = normalize_fulfillment_address((post.get("fulfillment_address_value") or "").strip())
    orp_ful = (post.get("fulfillment_orp") or "").strip()
    iczuj_ful = (post.get("fulfillment_iczuj") or "").strip()
    map_orp = (post.get("pio_outside_map_orp") or "").strip()
    map_iczuj = (post.get("pio_outside_map_iczuj") or "").strip()
    ico = (post.get("ico_value") or "").strip()
    company = (post.get("name_value") or "").strip()
    officer = (post.get("pio_officer_name") or "").strip()
    phone = (post.get("pio_officer_phone") or "").strip()
    email = (post.get("pio_officer_email") or "").strip()
    wt, suf = resolve_user_pio_waste_and_suffix_from_live_post(subject, post)
    return _build_user_pio_token_values(
        ico=ico,
        company=company,
        fac=fac,
        ful=ful,
        orp_ful=orp_ful,
        iczuj_ful=iczuj_ful,
        map_orp=map_orp,
        map_iczuj=map_iczuj,
        wt=wt,
        suf=suf,
        officer=officer,
        phone=phone,
        email=email,
    )


def build_user_pio_download_filename(
    subject: NameSubjectProfile,
    *,
    waste_suffix_pair: NameSubjectWasteSuffixPair | None = None,
) -> str:
    """Stažený soubor: ``kód_odpadu_Jméno_F_P_osoby_koncovka.xlsx``."""
    if waste_suffix_pair is not None:
        wt, suf = waste_suffix_pair.waste_type, waste_suffix_pair.suffix
    else:
        wt, suf = resolve_user_pio_waste_and_suffix(subject)
    fp_name = _pio_download_filename_fp_person_segment(subject)
    return f"{_user_pio_download_stem(wt, suf, fp_name)}.xlsx"


def generate_user_pio_xlsx_bytes(subject: NameSubjectProfile) -> bytes:
    """
    Excel z uživatelské šablony (``PIO_USER_XLSX_TEMPLATE`` / ``BASE_DIR/PIO.xlsx``).

    Vyžaduje vyřešený druh odpadu i koncovku — uložené v PIO nebo dopočítané z prvního vhodného páru.
    Dále musí být v sekci PIO vyplněné kontaktní údaje a výběr odpadu/koncovky na profilu.
    """
    if Workbook is None or load_workbook is None:
        raise RuntimeError("Knihovna openpyxl není nainstalovaná.")
    _raise_if_user_pio_export_minimum_missing_subject(subject)
    wt, suf = resolve_user_pio_waste_and_suffix(subject)
    if not wt or not suf:
        raise RuntimeError(
            "Chybí druh odpadu a koncovka: vyberte je v sekci PIO a uložte subjekt, "
            "nebo přidejte aspoň jeden řádek v části „Povolené odpady a koncovky“ a uložte."
        )
    tpl = template_path_for_user_pio()
    if not tpl:
        raise RuntimeError(
            "Chybí šablona PIO pro generování: umístěte soubor PIO.xlsx do kořene projektu "
            "(nebo nastavte PIO_USER_XLSX_TEMPLATE v settings)."
        )

    values = user_pio_placeholder_map(subject)
    wb = load_workbook(tpl)
    _replace_in_workbook(wb, values)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def generate_user_pio_xlsx_bytes_for_pair(
    subject: NameSubjectProfile,
    pair: NameSubjectWasteSuffixPair,
) -> bytes:
    """
    Stejná uživatelská šablona jako :func:`generate_user_pio_xlsx_bytes`
    (``PIO_USER_XLSX_TEMPLATE`` / ``BASE_DIR/PIO.xlsx``).

    Tokeny ``{{odpad}}``, ``{{koncovka}}`` atd. berou z **daného páru** odpad–koncovka;
    kontakt PIO musí být vyplněný na profilu subjektu (sekce PIO).
    """
    if Workbook is None or load_workbook is None:
        raise RuntimeError("Knihovna openpyxl není nainstalovaná.")
    wt, suf = pair.waste_type, pair.suffix
    if not wt or not suf:
        raise RuntimeError("Chybí druh odpadu nebo koncovka u páru.")
    tpl = template_path_for_user_pio()
    if not tpl:
        raise RuntimeError(
            "Chybí šablona PIO pro generování: umístěte soubor PIO.xlsx do kořene projektu "
            "(nebo nastavte PIO_USER_XLSX_TEMPLATE v settings)."
        )

    values = user_pio_placeholder_map(subject, waste_suffix_pair=pair)
    wb = load_workbook(tpl)
    _replace_in_workbook(wb, values)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_user_pio_download_filename_from_live_post(subject: NameSubjectProfile, post: QueryDict) -> str:
    wt, suf = resolve_user_pio_waste_and_suffix_from_live_post(subject, post)
    fp_name = _pio_download_filename_fp_person_segment(subject, post)
    return f"{_user_pio_download_stem(wt, suf, fp_name)}.xlsx"


def generate_user_pio_xlsx_bytes_from_live_post(subject: NameSubjectProfile, post: QueryDict) -> bytes:
    """
    Jako :func:`generate_user_pio_xlsx_bytes`, ale placeholdery z aktuálního POST formuláře
    (neuložený stav před náhledem / stažením).

    Platí stejné minimum ze sekce PIO jako u uloženého profilu (jméno, telefon, e-mail, druh odpadu, koncovka).
    """
    if Workbook is None or load_workbook is None:
        raise RuntimeError("Knihovna openpyxl není nainstalovaná.")
    _raise_if_user_pio_export_minimum_missing_post(post, subject)
    wt, suf = resolve_user_pio_waste_and_suffix_from_live_post(subject, post)
    if not wt or not suf:
        raise RuntimeError(
            "Chybí druh odpadu a koncovka: vyplňte je v sekci PIO nebo zajistěte odpovídající pár níže "
            "(výběr z uloženého seznamu párů)."
        )
    tpl = template_path_for_user_pio()
    if not tpl:
        raise RuntimeError(
            "Chybí šablona PIO pro generování: umístěte soubor PIO.xlsx do kořene projektu "
            "(nebo nastavte PIO_USER_XLSX_TEMPLATE v settings)."
        )

    values = user_pio_placeholder_map_from_live_post(subject, post)
    wb = load_workbook(tpl)
    _replace_in_workbook(wb, values)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
