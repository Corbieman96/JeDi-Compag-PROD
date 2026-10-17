import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ARES_URL = "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/{ico}"


def fetch_company_by_ico(ico: str) -> dict:
    """Load company data from ARES API by ICO."""
    request = Request(
        ARES_URL.format(ico=ico),
        headers={"User-Agent": "Jedis-Django/1.0"},
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("ARES služba je dočasně nedostupná.") from exc

    sidlo = payload.get("sidlo", {})
    sidlo_parts = [
        sidlo.get("nazevUlice"),
        sidlo.get("cisloDomovni"),
        sidlo.get("cisloOrientacni"),
        sidlo.get("nazevObce"),
        sidlo.get("psc"),
    ]
    address = " ".join(str(part) for part in sidlo_parts if part)
    return {
        "ico": payload.get("ico", ico),
        "company_name": payload.get("obchodniJmeno", ""),
        "address": address.strip(),
    }
