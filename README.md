# LoL Scout

Aplicacion de escritorio en Python para Windows que consulta fuentes externas de estadisticas y muestra:

- Historial reciente de partidas
- Winrate
- Elo/rango
- KDA, campeones y resumen de rendimiento

## Requisitos

- Python 3.11 o superior

## Instalacion

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Para cargar automaticamente los avatares de Discord del ranking en desarrollo, crea un archivo `.env` en la raiz del proyecto con:

```env
DISCORD_BOT_TOKEN=tu_bot_token
DISCORD_GUILD_ID=tu_server_id
```

La app tambien intentara leer `.env` junto al ejecutable si la lanzas desde `dist\LoLScout.exe`.

## Ejecutable autosuficiente

`build_exe.bat` ahora hace esto antes de compilar:

- lee `userdc_id.json`
- descarga los avatares de Discord usando el `.env`
- los empaqueta dentro del ejecutable

Resultado:

- puedes pasar solo `dist\LoLScout.exe`
- el PC destino no necesita `.env`
- el token no queda distribuido junto al ejecutable como archivo separado

Para que ese build funcione, en el PC donde compilas si necesitas tener `.env`.

## Uso

1. Abre la app.
2. Escribe el Riot ID del jugador:
   - Nombre
   - Tag
3. Elige la region/plataforma.
4. Pulsa `Buscar`.

La configuracion incluye un campo de API Key por compatibilidad con versiones anteriores, pero la app ya no depende de Riot API.

El apartado de ranking usa una ruta rapida sin Riot API y cache local en `.lolscout_cache` durante 5 minutos para minimizar tiempos de carga en refrescos repetidos.

## Crear .exe para Windows

```powershell
build_exe.bat
```

El ejecutable quedara en `dist\LoLScout.exe`.
