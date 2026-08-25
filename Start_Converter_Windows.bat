@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 rapidraw_preset_migrator.py
) else (
  python rapidraw_preset_migrator.py
)
if errorlevel 1 pause
