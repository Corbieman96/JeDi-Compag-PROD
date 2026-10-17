"""Stažení portable LibreOffice pro převod XLSX→PDF bez admin instalace."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings

PORTABLE_INSTALLER_URL = (
    "https://download.portableapps.com/portableapps/LibreOfficePortable/"
    "LibreOfficePortable_26.2.1_MultilingualStandard.paf.exe"
)
DEFAULT_INSTALL_DIR = Path(settings.BASE_DIR) / "tools" / "LibreOfficePortable"


def portable_soffice_path(install_dir: Path | None = None) -> Path | None:
    root = install_dir or DEFAULT_INSTALL_DIR
    matches = sorted(root.rglob("soffice.exe"))
    return matches[0] if matches else None


def _download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    curl = shutil.which("curl") or shutil.which("curl.exe")
    if curl:
        result = subprocess.run(
            [curl, "-L", "-o", str(dest), url],
            capture_output=True,
            text=True,
            check=False,
            timeout=900,
        )
        if result.returncode == 0 and dest.is_file() and dest.stat().st_size > 0:
            return
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            "Stažení portable LibreOffice selhalo (curl)."
            + (f" {detail}" if detail else "")
        )

    import urllib.request

    try:
        urllib.request.urlretrieve(url, dest)
    except OSError as exc:
        raise RuntimeError(
            "Stažení portable LibreOffice selhalo. "
            "Nainstalujte LibreOffice ručně nebo spusťte curl."
        ) from exc


def install_portable_libreoffice(
    install_dir: Path | None = None,
    *,
    installer_url: str = PORTABLE_INSTALLER_URL,
) -> Path:
    target = (install_dir or DEFAULT_INSTALL_DIR).resolve()
    existing = portable_soffice_path(target)
    if existing is not None:
        return existing

    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        installer = Path(tmp) / "LibreOfficePortable.paf.exe"
        _download_file(installer_url, installer)
        cmd = [
            str(installer),
            f"/D={target}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=900)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(
                "Instalace portable LibreOffice selhala."
                + (f" {detail}" if detail else "")
            )

    soffice = portable_soffice_path(target)
    if soffice is None:
        raise RuntimeError(
            f"Portable LibreOffice není v {target} — chybí soffice.exe."
        )
    return soffice
