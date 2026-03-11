# LoL Scout

Aplicacion de escritorio en Python para Windows que consulta la API oficial de Riot Games y muestra:

- Historial reciente de partidas
- Winrate
- Elo/rango
- MMR estimado
- KDA, campeones y resumen de rendimiento

## Requisitos

- Python 3.11 o superior
- Una API Key de Riot Games: https://developer.riotgames.com/

## Instalacion

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Uso

1. Abre la app.
2. Introduce tu Riot API Key.
3. Escribe el Riot ID del jugador:
   - Nombre
   - Tag
4. Elige la region/plataforma.
5. Pulsa `Buscar`.

La aplicacion incluye una API Key precargada por defecto. Si caduca, puedes sustituirla desde la propia interfaz o cambiar el valor por defecto en `src/lolscout/config.py`.

La API oficial no expone el MMR real. La aplicacion muestra un `MMR estimado` calculado a partir del rango actual, LP y rendimiento reciente.

## Crear .exe para Windows

```powershell
build_exe.bat
```

El ejecutable quedara en `dist\LoLScout\LoLScout.exe`.
