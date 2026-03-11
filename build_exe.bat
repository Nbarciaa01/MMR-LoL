@echo off
setlocal

if not exist .venv (
    python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

pyinstaller ^
  --noconfirm ^
  --clean ^
  --name LoLScout ^
  --windowed ^
  --add-data "src\\lolscout;src\\lolscout" ^
  main.py

echo.
echo Build completada. Ejecutable disponible en dist\LoLScout\LoLScout.exe
endlocal
