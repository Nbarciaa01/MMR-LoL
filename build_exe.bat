@echo off
setlocal

if not exist .venv (
    python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python scripts\fetch_discord_avatars.py

pyinstaller ^
  --noconfirm ^
  --clean ^
  --name LoLScout ^
  --onefile ^
  --windowed ^
  --add-data "src\\lolscout;src\\lolscout" ^
  --add-data "userdc_id.json;." ^
  --add-data "discord_avatars;discord_avatars" ^
  main.py

echo.
echo Build completada. Ejecutable disponible en dist\LoLScout.exe
endlocal
