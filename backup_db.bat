@echo off
REM Denni zaloha hlavni DB do adresare Zaloha_db (viz core/services/db_backup.py)
cd /d C:\Jedi_2_0
".\.venv\Scripts\python.exe" manage.py backup_db
