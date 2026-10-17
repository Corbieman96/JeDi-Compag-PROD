"""Příprava šablony jizda.xlsm — oboustranný tisk a makro TiskCelySesit (celý sešit)."""

from __future__ import annotations

from pathlib import Path

from waste_docs.services.reports.excel_template_duplex import (
    PRINT_BOTH_SIDES_LONG_EDGE,
    PRINT_BOTH_SIDES_SHORT_EDGE,
    apply_duplex_via_excel,
)
from waste_docs.services.reports.protocol_print_settings import (
    PROTOCOL_PRINT_MACRO_NAME,
    template_has_printer_settings,
    template_has_vba_project,
)

PROTOCOL_PRINT_MACRO_VBA = f"""Sub {PROTOCOL_PRINT_MACRO_NAME}()
    ActiveWorkbook.PrintOut Copies:=1, Collate:=True
End Sub
"""

XL_OPENXML_WORKBOOK_MACRO_ENABLED = 52
_VBA_STD_MODULE = 1


def _save_xlsm_with_print_macro(
    source_xlsx: Path,
    target_xlsm: Path,
    *,
    short_edge: bool = False,
) -> None:
    try:
        import win32com.client  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError(
            "Balíček pywin32 není nainstalovaný. Spusťte: pip install pywin32"
        ) from exc

    duplex_mode = PRINT_BOTH_SIDES_SHORT_EDGE if short_edge else PRINT_BOTH_SIDES_LONG_EDGE
    excel = None
    workbook = None
    try:
        try:
            excel = win32com.client.DispatchEx("Excel.Application")
        except Exception as exc:
            raise RuntimeError(
                "Microsoft Excel není dostupný (COM). Nainstalujte MS Excel pro vytvoření jizda.xlsm s makrem."
            ) from exc
        excel.Visible = False
        excel.DisplayAlerts = False
        workbook = excel.Workbooks.Open(str(source_xlsx.resolve()))
        for sheet in workbook.Worksheets:
            sheet.PageSetup.PrintOnBothSides = duplex_mode
            sheet.PageSetup.Orientation = 2

        try:
            vbproj = workbook.VBProject
            has_macro = False
            for comp in vbproj.VBComponents:
                if comp.Type != _VBA_STD_MODULE:
                    continue
                line_count = comp.CodeModule.CountOfLines
                if line_count < 1:
                    continue
                code = comp.CodeModule.Lines(1, line_count)
                if PROTOCOL_PRINT_MACRO_NAME in code:
                    has_macro = True
                    break
            if not has_macro:
                module = vbproj.VBComponents.Add(_VBA_STD_MODULE)
                module.Name = "JizdaPrint"
                module.CodeModule.AddFromString(PROTOCOL_PRINT_MACRO_VBA)
        except Exception as exc:
            raise RuntimeError(
                "Nelze vložit makro TiskCelySesit. V Microsoft Excel zapněte "
                "Soubor → Možnosti → Centrum zabezpečení → Nastavení center zabezpečení → "
                "Nastavení maker → zaškrtněte „Důvěřovat přístupu k modelu objektu VBA projektu“."
            ) from exc

        if target_xlsm.is_file():
            target_xlsm.unlink()
        workbook.SaveAs(str(target_xlsm.resolve()), FileFormat=XL_OPENXML_WORKBOOK_MACRO_ENABLED)
    finally:
        if workbook is not None:
            workbook.Close(SaveChanges=False)
        if excel is not None:
            excel.Quit()


def ensure_jizda_print_template(
    base_dir: Path | None = None,
    *,
    short_edge: bool = False,
) -> tuple[Path, list[str]]:
    """
    Připraví jizda.xlsx (duplex) a jizda.xlsm (makro TiskCelySesit).

    Vrací (hlavní šablona pro resolve_protocol_template_path, seznam varování).
    """
    from django.conf import settings

    base = Path(base_dir or settings.BASE_DIR)
    xlsx_path = base / "jizda.xlsx"
    xlsm_path = base / "jizda.xlsm"
    if not xlsx_path.is_file():
        raise FileNotFoundError(f"Šablona neexistuje: {xlsx_path}")

    notes: list[str] = []
    apply_duplex_via_excel(xlsx_path, short_edge=short_edge)
    if not template_has_printer_settings(xlsx_path):
        raise RuntimeError(
            f"Excel neuložil printerSettings do {xlsx_path}. "
            "Otevřete šablonu v MS Excel, nastavte Tisk na obě strany a uložte ručně."
        )

    try:
        _save_xlsm_with_print_macro(xlsx_path, xlsm_path, short_edge=short_edge)
    except RuntimeError as exc:
        notes.append(str(exc))
    else:
        if not template_has_vba_project(xlsm_path):
            notes.append(
                f"Makro se nepodařilo ověřit v {xlsm_path.name}. "
                f"Přidejte ručně Sub {PROTOCOL_PRINT_MACRO_NAME}() s ActiveWorkbook.PrintOut."
            )

    primary = xlsm_path if xlsm_path.is_file() and template_has_vba_project(xlsm_path) else xlsx_path
    return primary, notes
