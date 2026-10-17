# JeDiS

JeDiS (Jednoduchý dispečerský systém) je interní Django aplikace pro řízení svozu a přepravy odpadů.

## Provozní prostředí

| Prostředí | Složka | URL |
| --- | --- | --- |
| PROD | `C:\Jedi_2_0\JeDis-PROD` | `http://192.168.1.18:8000` |
| TEST | `C:\Jedi_2_0\JeDis-TEST` | `http://192.168.1.18:8001` |

Obě prostředí používají vlastní `.env`, `db.sqlite3`, `addresses.sqlite3`, `media/`, `staticfiles/` a `logs/`. Sdílejí pouze Python prostředí `C:\Jedi_2_0\.venv`.

## Bezpečnost dat

Do Gitu nikdy nepatří `.env`, databáze, soubory v `media/`, logy ani zálohy. Před migrací nebo nasazením do PROD vždy vytvořte zálohu databáze a uživatelských souborů.

## Základní kontroly

```powershell
C:\Jedi_2_0\.venv\Scripts\python.exe manage.py check
C:\Jedi_2_0\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
C:\Jedi_2_0\.venv\Scripts\python.exe -m pytest
```

Provozní skripty a instalace trvalého spuštění jsou popsány v `scripts/README-server.md`.
