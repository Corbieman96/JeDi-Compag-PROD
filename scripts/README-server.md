# Trvalé spuštění na Windows

Aplikace je připravená jako dvě úlohy Plánovače úloh Windows (`JeDiS PROD` a `JeDiS TEST`). Úlohy se spouštějí při startu serveru, běží i po odhlášení uživatele a dohledový skript Uvicorn po pádu znovu spustí. Uvicorn běží bez `--reload`.

## Instalace

Otevřete **Windows PowerShell jako správce** a spusťte:

```powershell
Set-Location C:\Jedi_2_0
.\JeDis-PROD\scripts\manage_server_tasks.ps1 -Action Install
.\JeDis-PROD\scripts\manage_server_tasks.ps1 -Action Start
```

Při instalaci zadejte Windows účet, pod kterým dříve fungoval převod přes MS Excel. Heslo ukládá chráněně Plánovač úloh Windows; není uloženo v projektu. Pokud Excel není potřeba, lze instalovat pod `SYSTEM` přepínačem `-RunAsSystem`.

Instalátor vytvoří také pravidla firewallu pro TCP 8000 a 8001, omezená na lokální podsíť.

## Správa

```powershell
.\JeDis-PROD\scripts\manage_server_tasks.ps1 -Action Status
.\JeDis-PROD\scripts\manage_server_tasks.ps1 -Action Stop
.\JeDis-PROD\scripts\manage_server_tasks.ps1 -Action Start
```

Logy jsou odděleně v `JeDis-PROD\logs\` a `JeDis-TEST\logs\`. Při ručním spuštění lze použít `start_server_only.bat`; zavření jeho okna ruční instanci ukončí.
