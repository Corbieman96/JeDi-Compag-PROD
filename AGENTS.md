# Projektová pravidla pro vývoj

## Autorská práva
JeDiS — Jednoduchý Dispečerský Systém (průvodky, ZPO, PIO, plán svozů, dashboard, číselníky, tisk). © Holub Stanislav

## Architektura a modularita
- Nová funkce = nový modul (nevkládat novou doménovou logiku do existujícího nesouvisejícího souboru).
- Udržovat soubory malé a přehledné; při růstu je rozdělit do podsložek (`forms/`, `services/`, `views/`, `validation/`, `templates/`).
- Sdílené utility držet odděleně od business logiky.

## UI a styl
- Držet jednotný grafický režim projektu (Compag styl: zelená paleta, jednotné komponenty, konzistentní tlačítka/karty/tabulky).
- Nové stránky a formuláře musí používat centrální layout a stejné vizuální prvky.
- Významové **UI signály** (konflikt, stav řádku, nápověda při výběru ze seznamu) u nových funkcí: logika výpočtu v **samostatném service modulu** pod příslušnou aplikací/view jen předá data do šablony; barvy a typografie **Compag**. U `<select>` počítejte s **nevyzpytatelným stylováním `<option>` v prohlížečích** — vždy doplňte `title`, případně krátký **prefix v textu** položky.

## Implementační zásady
- Každou větší funkci navrhnout modulárně už od začátku (bez dočasných monolitických řešení).
- Před přidáním nové logiky zkontrolovat, zda nejde použít existující sdílený modul; pokud ne, vytvořit nový.

## Exporty (XLSX / CSV)
- Logika exportu patří do **`{app}/services/reports/`** (např. `waste_docs/services/reports/`). View jen ověří přihlášení, oprávnění a zavolá `build_*_bytes` + odpověď.
- **Stejný výběr dat jako u seznamu:** sdílená funkce pro QuerySet (žádné duplicitní kopírování filtrů z GET).
- **Sloupce exportu** definovat na jednom místě v modulu (registry / seznam hlaviček + getterů), aby šlo sloupec přidat úpravou jednoho souboru.
- **Limit řádků** u velkých exportů (např. 10 000); při oříznutí informovat v listu (`jizdy_list_export`).
- **HTTP odpověď:** `content_type` pro XLSX a `Content-Disposition` přes `django.utils.http.content_disposition_header`; pro waste_docs společná utilita [`waste_docs/services/reports/http.py`](waste_docs/services/reports/http.py) (`xlsx_attachment_response`).
- **URL:** konzistentně pod appkou (např. `/waste-docs/list/jizdy.xlsx`); odkaz v UI předává **stejné GET parametry** jako aktuální filtr seznamu.
- Report přes více aplikací → `core/services/reports/`.

Reference implementace: export jízd — [`waste_docs/services/reports/jizdy_list_export.py`](waste_docs/services/reports/jizdy_list_export.py), filtry seznamu — [`waste_docs/services/pruvodka_list_filters.py`](waste_docs/services/pruvodka_list_filters.py).
python manage.py runserver 192.168.68.60:8000
192.168.68.62
python manage.py runserver 192.168.1.162:8001

Set-Location D:\Jedis_2_0
.\.venv\Scripts\python.exe manage.py runserver 192.168.1.162:8001

,/address-data/ sem by se měli načíst Ulice, čísla popisné, Města , prost  vše aby tady byl ofline databze českých adres  .. vpodatě by se mělo s openstreet map načíst to co se zde zadává address-data/new/ ( a to by mělo mít češtinu mimochodem) uložíš komplení seznam adresa pro města .. !! chápeš