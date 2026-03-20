@echo off
setlocal

cd /d "%~dp0"

if not exist .venv (
    python -m venv .venv
    if errorlevel 1 goto :error
)

call .venv\Scripts\activate.bat
if errorlevel 1 goto :error

python -m pip install --upgrade pip
if errorlevel 1 goto :error

pip install -r requirements.txt
if errorlevel 1 goto :error

python scripts\generate_app_icon.py
if errorlevel 1 goto :error

python scripts\fetch_discord_avatars.py
if errorlevel 1 goto :error

if exist dist\LoLScout rmdir /s /q dist\LoLScout
if exist build\LoLScout rmdir /s /q build\LoLScout
if exist build\MMRlol rmdir /s /q build\MMRlol
if exist dist\LoLScout.exe del /q dist\LoLScout.exe
if exist dist\MMRlol.exe del /q dist\MMRlol.exe

pyinstaller --noconfirm --clean LoLScout.spec
if errorlevel 1 goto :error

echo.
echo Build completada. Ejecutable autosuficiente en dist\MMRlol.exe
endlocal
exit /b 0

:error
echo.
echo Build fallida.
endlocal
exit /b 1
