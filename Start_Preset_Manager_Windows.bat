@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 preset_manager.py "%~dp0migration_catalog.json"
) else (
  python preset_manager.py "%~dp0migration_catalog.json"
)
if errorlevel 1 pause
