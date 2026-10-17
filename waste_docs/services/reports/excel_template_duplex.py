"""Nastavení oboustranného / jednostranného tisku ve šabloně jizda.xlsx přes Microsoft Excel (Windows)."""

from __future__ import annotations

from pathlib import Path

# Excel constants — xlPrintOnBothSidesLongEdge / ShortEdge
PRINT_BOTH_SIDES_LONG_EDGE = 1
PRINT_BOTH_SIDES_SHORT_EDGE = 2
PRINT_ON_BOTH_SIDES_NONE = 0


def apply_simplex_via_excel(template_path: Path) -> None:
    """Vypne oboustranný tisk ve šabloně (PrintOnBothSides = None / 0)."""
    try:
        import win32com.client  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError(
            "Balíček pywin32 není nainstalovaný. Spusťte: pip install pywin32"
        ) from exc

    path = Path(template_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Šablona neexistuje: {path}")

    excel = None
    workbook = None
    try:
        try:
            excel = win32com.client.DispatchEx("Excel.Application")
        except Exception as exc:
            raise RuntimeError(
                "Microsoft Excel není dostupný (COM). Použijte prepare_jizda_simplex_template "
                "bez Excelu, nebo v Excelu ručně vypněte Tisk na obě strany u jizda.xlsx."
            ) from exc
        excel.Visible = False
        excel.DisplayAlerts = False
        workbook = excel.Workbooks.Open(str(path))
        for sheet in workbook.Worksheets:
            sheet.PageSetup.PrintOnBothSides = PRINT_ON_BOTH_SIDES_NONE
            sheet.PageSetup.Orientation = 2  # xlLandscape
            sheet.PageSetup.PrintArea = "A1:M38"
        workbook.Save()
    finally:
        if workbook is not None:
            workbook.Close(SaveChanges=True)
        if excel is not None:
            excel.Quit()


def apply_duplex_via_excel(template_path: Path, *, short_edge: bool = False) -> None:
    """Uloží do šablony printerSettings pomocí Excel COM API."""
    from waste_docs.services.reports.protocol_print_settings import template_has_printer_settings

    try:
        import win32com.client  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError(
            "Balíček pywin32 není nainstalovaný. Spusťte: pip install pywin32"
        ) from exc

    path = Path(template_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Šablona neexistuje: {path}")

    duplex_mode = PRINT_BOTH_SIDES_SHORT_EDGE if short_edge else PRINT_BOTH_SIDES_LONG_EDGE
    excel = None
    workbook = None
    try:
        try:
            excel = win32com.client.DispatchEx("Excel.Application")
        except Exception as exc:
            raise RuntimeError(
                "Microsoft Excel není dostupný (COM). Nainstalujte MS Excel a spusťte příkaz znovu, "
                "nebo v Excelu ručně nastavte Tisk na obě strany u jizda.xlsx a uložte."
            ) from exc
        excel.Visible = False
        excel.DisplayAlerts = False
        workbook = excel.Workbooks.Open(str(path))
        for sheet in workbook.Worksheets:
            sheet.PageSetup.PrintOnBothSides = duplex_mode
            sheet.PageSetup.Orientation = 2  # xlLandscape
        workbook.Save()
    finally:
        if workbook is not None:
            workbook.Close(SaveChanges=True)
        if excel is not None:
            excel.Quit()

    if not template_has_printer_settings(path):
        raise RuntimeError(
            f"Excel neuložil oboustranný tisk (printerSettings) do souboru {path.name}. "
            "Otevřete šablonu v MS Excel, zvolte Rozložení → Tisk na obě strany (otočení přes delší hranu) "
            "a soubor uložte."
        )
