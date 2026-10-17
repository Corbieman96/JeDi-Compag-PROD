"""Důvěryhodný jednostranný printerSettings blob (DEVMODE) pro protokol jízdy."""

from __future__ import annotations

import struct
from pathlib import Path

DM_DUPLEX = 0x1000
DMDUP_SIMPLEX = 1
DMDUP_VERTICAL = 2
DMDUP_HORIZONTAL = 3
TEMPLATE_BLOB_MIN_SIZE = 220
TRUSTED_BLOB_MIN_SIZE = 256

_DATA_DIR = Path(__file__).resolve().parent / "data"
RICOH_SIMPLEX_BLOB_PATH = _DATA_DIR / "ricoh_im_c300_simplex.bin"


def devmode_duplex_value(blob: bytes) -> int | None:
    if len(blob) < 96:
        return None
    fields = struct.unpack_from("<I", blob, 72)[0]
    if not (fields & DM_DUPLEX):
        return None
    return struct.unpack_from("<H", blob, 94)[0]


def is_trusted_simplex_printer_settings_blob(blob: bytes) -> bool:
    """Reálný DEVMODE od ovladače (>=256 B) se dmDuplex=1."""
    if len(blob) < TRUSTED_BLOB_MIN_SIZE:
        return False
    return struct.unpack_from("<H", blob, 94)[0] == DMDUP_SIMPLEX


def is_simplex_printer_settings_blob(blob: bytes) -> bool:
    return is_trusted_simplex_printer_settings_blob(blob)


def read_trusted_simplex_blob_file(path: Path) -> bytes | None:
    if not path.is_file():
        return None
    blob = path.read_bytes()
    if is_trusted_simplex_printer_settings_blob(blob):
        return blob
    return None


def devmode_duplex_at_offset(blob: bytes) -> int | None:
    if len(blob) < 96:
        return None
    return struct.unpack_from("<H", blob, 94)[0]


def is_duplex_printer_settings_blob(blob: bytes) -> bool:
    duplex = devmode_duplex_at_offset(blob)
    return duplex in (DMDUP_VERTICAL, DMDUP_HORIZONTAL)


def is_simplex_template_blob(blob: bytes) -> bool:
    """Jednostranný blob ze šablony jizda.xlsx (Excel / prepare)."""
    if len(blob) < TEMPLATE_BLOB_MIN_SIZE:
        return False
    return devmode_duplex_at_offset(blob) == DMDUP_SIMPLEX


def resolve_simplex_blob_from_template(template_blob: bytes | None) -> bytes | None:
    """Jen ze šablony — generátor nepoužívá fallback soubor v data/."""
    if template_blob and is_simplex_template_blob(template_blob):
        return template_blob
    return None


def resolve_trusted_simplex_blob(template_blob: bytes | None) -> bytes | None:
    """Pro prepare/capture — šablona nebo fallback soubor v data/."""
    if template_blob and is_trusted_simplex_printer_settings_blob(template_blob):
        return template_blob
    return read_trusted_simplex_blob_file(RICOH_SIMPLEX_BLOB_PATH)


def capture_simplex_blob_for_ricoh(printer_needle: str = "RICOH") -> bytes:
    printer_name = find_printer_by_substring(printer_needle)
    if not printer_name:
        raise RuntimeError(
            f"Nenalezena tiskárna odpovídající {printer_needle!r}. "
            "Nainstalujte ovladač RICOH IM C300 PCL 6 (i síťová tiskárna)."
        )
    return capture_simplex_devmode_for_printer(printer_name)


def find_printer_by_substring(name_part: str) -> str | None:
    try:
        import win32print
    except ImportError:
        return None
    needle = name_part.casefold()
    for item in win32print.EnumPrinters(
        win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    ):
        name = item[2]
        if needle in name.casefold():
            return name
    return None


def capture_simplex_devmode_for_printer(printer_name: str) -> bytes:
    """Zachytí DEVMODE přes Windows spooler (DocumentProperties)."""
    import ctypes
    from ctypes import wintypes

    try:
        import win32con
        import win32print
    except ImportError as exc:
        raise RuntimeError("Balíček pywin32 není nainstalovaný.") from exc

    winspool = ctypes.WinDLL("winspool.drv")
    document_properties = winspool.DocumentPropertiesW
    document_properties.argtypes = [
        wintypes.HWND,
        wintypes.HANDLE,
        wintypes.LPCWSTR,
        ctypes.POINTER(ctypes.c_byte),
        ctypes.POINTER(ctypes.c_byte),
        wintypes.DWORD,
    ]
    document_properties.restype = wintypes.LONG

    handle = win32print.OpenPrinter(printer_name)
    handle_val = int(handle)
    try:
        size = document_properties(0, handle_val, printer_name, None, None, 0)
        if size <= 0:
            raise RuntimeError(f"Tiskárna {printer_name!r}: DocumentProperties vrátilo {size}.")

        in_buf = (ctypes.c_byte * size)()
        rc = document_properties(
            0,
            handle_val,
            printer_name,
            None,
            in_buf,
            win32con.DM_OUT_BUFFER,
        )
        dm_size = struct.unpack_from("<H", in_buf, 68)[0]
        if dm_size == 0 and rc not in (win32con.IDOK, size):
            raise RuntimeError(
                f"Tiskárna {printer_name!r}: nelze načíst výchozí DEVMODE (kód {rc})."
            )

        fields = struct.unpack_from("<I", in_buf, 72)[0]
        fields |= win32con.DM_DUPLEX | win32con.DM_ORIENTATION | win32con.DM_PAPERSIZE
        struct.pack_into("<I", in_buf, 72, fields)
        struct.pack_into("<H", in_buf, 94, win32con.DMDUP_SIMPLEX)
        struct.pack_into("<H", in_buf, 76, win32con.DMORIENT_LANDSCAPE)
        struct.pack_into("<H", in_buf, 78, win32con.DMPAPER_A4)

        out_buf = (ctypes.c_byte * size)()
        rc = document_properties(
            0,
            handle_val,
            printer_name,
            in_buf,
            out_buf,
            win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER,
        )
        merged_size = struct.unpack_from("<H", out_buf, 68)[0]
        if merged_size == 0 and rc not in (win32con.IDOK, size):
            raise RuntimeError(
                f"Tiskárna {printer_name!r}: nelze sloučit jednostranný DEVMODE (kód {rc})."
            )

        blob = bytes(out_buf)
        if not is_trusted_simplex_printer_settings_blob(blob):
            duplex = struct.unpack_from("<H", blob, 94)[0]
            raise RuntimeError(
                f"DEVMODE z {printer_name!r} není jednostranný (dmDuplex={duplex}, len={len(blob)})."
            )
        return blob
    finally:
        win32print.ClosePrinter(handle)


def save_trusted_simplex_blob(blob: bytes, path: Path | None = None) -> Path:
    target = Path(path) if path is not None else RICOH_SIMPLEX_BLOB_PATH
    if not is_trusted_simplex_printer_settings_blob(blob):
        raise ValueError("Blob není důvěryhodný jednostranný DEVMODE.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(blob)
    return target
