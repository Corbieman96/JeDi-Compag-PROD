"""Sdílený HTTP klient pro Overpass API."""

from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def load_overpass_json(
    query: str,
    *,
    timeout: int = 30,
    max_attempts: int | None = None,
    user_agent: str = "Jedis-Django/1.0 (offline-address-import)",
) -> dict | None:
    """
    Odešle Overpass QL dotaz. Při chybě zkusí další endpoint / další pokus.
    max_attempts=None → projít všechny URL (typicky import).
    """
    payload = urlencode({"data": query}).encode("utf-8")
    endpoints = list(OVERPASS_URLS)
    if max_attempts is not None:
        endpoints = endpoints[: max(1, max_attempts)]

    last_error: Exception | None = None
    for endpoint in endpoints:
        req = Request(
            endpoint,
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                "User-Agent": user_agent,
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            last_error = exc
            time.sleep(0.4)
            continue
    _ = last_error
    return None
