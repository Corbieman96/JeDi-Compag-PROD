import re
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from catalogs.services.address import normalize_czech_address


VISOH2_SEARCH_URL = "https://visoh2.mzp.cz/Zarizeni/ZarizeniVyhledatGrid"


def _clean_html_text(value: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", value or "")
    compact = re.sub(r"\s+", " ", unescape(no_tags)).strip()
    return compact


def _extract_detail_key(link_cell: str) -> str:
    match = re.search(r"/Zarizeni/Zarizeni/Detail/([a-f0-9]+)", link_cell or "", flags=re.IGNORECASE)
    return match.group(1) if match else ""


def _extract_rows(html: str) -> list[dict]:
    rows: list[dict] = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.IGNORECASE | re.DOTALL):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, flags=re.IGNORECASE | re.DOTALL)
        if len(cells) < 6:
            continue
        ics = _clean_html_text(cells[5])
        # Skip headers/empty rows
        if not ics or not re.search(r"\d{8}", ics):
            continue
        detail_key = _extract_detail_key(cells[0])
        icz = _clean_html_text(cells[1])
        facility_type = _clean_html_text(cells[2])
        address = normalize_czech_address(_clean_html_text(cells[3]))
        operator = _clean_html_text(cells[4])
        ico_match = re.search(r"\d{8}", ics)
        ico = ico_match.group(0) if ico_match else ""
        rows.append(
            {
                "detail_key": detail_key,
                "icz": icz,
                "facility_type": facility_type,
                "address": address,
                "name": operator,
                "ico": ico,
                "zuj": "",
            }
        )
    return rows


def fetch_subjects_by_ico(ico: str) -> list[dict]:
    """Load VISOH2 registry rows by ICO from public grid page."""
    params = urlencode(
        {
            "TF.ICO": ico,
            "TF.PlatnostProvozovatele": "AktualnePlatny",
            "TF.PlatnostOdpadu": "AktualnePlatny",
            "TF.PlatnostCinnosti": "AktualnePlatny",
            "TF.NebezpecnyOdpad": "false",
            "TF.collapsed": "0",
            "reload": "1",
            # VISOH2 stránkuje výchozí výstup (typicky 10 řádků),
            # takže bez tohoto parametru chybí část zařízení.
            "rows": "50",
        }
    )
    request = Request(
        f"{VISOH2_SEARCH_URL}?{params}",
        headers={"User-Agent": "Jedis-Django/1.0"},
    )
    try:
        with urlopen(request, timeout=12) as response:
            html = response.read().decode("utf-8", errors="ignore")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError("VISOH2 služba je dočasně nedostupná.") from exc

    rows = fetch_rows_from_html(html)
    return rows


def fetch_rows_from_html(html: str) -> list[dict]:
    rows = _extract_rows(html)
    if not rows:
        raise RuntimeError("VISOH2 nevrátil žádné záznamy pro zadané IČO.")
    return rows
