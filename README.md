# MMR LoL

Aplicacion de escritorio y web orientada a seguir un grupo cerrado de jugadores de League of Legends desde una sola interfaz.

La app combina varias fuentes externas para mostrar:

- balance diario de LP en SoloQ
- ranking del grupo por elo y MMR estimado
- builds y matchups desde Lolalytics
- partidas activas en vivo
- galeria visual de jugadores
- enlaces rapidos a perfiles y partidas en vivo

El proyecto esta construido con `Python` + `PySide6` y se distribuye como ejecutable autosuficiente `MMRlol.exe`.

## Que hace la app

### 1. Hoy

La pestana **Hoy** calcula el balance diario de LP de los jugadores configurados.

Incluye:

- LP netos del dia
- rango actual
- ultimas partidas jugadas hoy
- deteccion de partidas de **SoloQ** desde las `00:00` locales

La logica usa snapshots locales y datos obtenidos mediante scraping de fuentes publicas.

### 2. Ranking

La pestana **Ranking** construye una clasificacion del grupo con informacion como:

- elo/rango de SoloQ
- LP actuales
- MMR estimado
- numero de partidas
- campeones mas jugados
- roles mas frecuentes

Tambien carga avatares de Discord y assets visuales para que la vista sea mas parecida a una dashboard privada que a una tabla basica.

### 3. Galeria de jugadores

La galeria crea tarjetas visuales por cuenta usando:

- campeon con mas maestria
- splash/loading screen
- avatar de Discord si existe mapeo
- detalles rapidos de la cuenta

Es una capa mas estetica, pensada para presentar al grupo de forma visual.

### 4. En partida

La pestana **En partida** detecta partidas activas y muestra:

- campeon
- rol estimado
- winrate reciente
- datos resumidos del jugador
- composicion de equipos

Tambien enlaza a la vista publica de partida en vivo cuando la fuente la expone.

### 5. Builds

La seccion **Builds** consume datos de Lolalytics y permite consultar:

- catalogo de campeones
- build principal
- runas
- hechizos
- orden de habilidades
- objetos por slot
- mejores y peores matchups

Esta pensada como una herramienta rapida de consulta, no como sustituto completo del navegador.

## Fuentes de datos

La app mezcla varias fuentes para cubrir casos distintos:

- `LeagueOfGraphs`: perfil, historial reciente, habitos de SoloQ y datos de apoyo
- `OP.GG`: ranked, historico de LP y perfiles publicos
- `U.GG`: apoyo para algunos datos agregados
- `Lolalytics`: builds, runas, itemizacion y counters
- `Porofessor`: apoyo para partida en vivo en algunos casos
- `Discord CDN/API`: avatares del grupo durante el build

## Requisitos

### Desarrollo

- Windows
- Python `3.11+`
- conexion a internet

### Uso desde ejecutable

Para el usuario final solo hace falta:

- `MMRlol.exe`
- conexion a internet

No necesita instalar Python ni copiar carpetas adicionales.

## Instalacion en desarrollo

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Version web

La migracion web reutiliza la logica existente y sirve tanto la API como la interfaz desde el mismo proceso. La clave de Riot solo se lee en el servidor y nunca se entrega al navegador.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-web.txt
Copy-Item .env.example .env
python -m uvicorn src.lolscout.web_app:app --reload --host 127.0.0.1 --port 8000
```

Configura en `.env` una clave nueva de desarrollo mientras construyes el prototipo:

```env
RIOT_API_KEY=RGAPI-tu-clave
```

La web queda disponible en `http://127.0.0.1:8000`. La documentacion de sus endpoints esta en `http://127.0.0.1:8000/docs`.

Para publicar el proyecto hace falta desplegar este servidor en un proveedor que admita Python, guardar `RIOT_API_KEY` como secreto del proveedor y solicitar a Riot una clave de produccion antes de abrir el acceso al publico.

## Configuracion

La app guarda su configuracion en:

`%APPDATA%\LoLScout\config.json`

Entre otras cosas se almacenan:

- plataforma por defecto
- jugadores del grupo

## Riot API y scraping publico

La version web usa la API oficial de Riot para Ranking, Hoy y En partida cuando `RIOT_API_KEY` esta configurada. Match-V5 obtiene las partidas SoloQ del dia y Spectator-V5 consulta las partidas activas. Si Riot no esta disponible, el modo automatico recurre al sistema anterior.

Las claves de desarrollo de Riot caducan cada 24 horas. No deben incluirse en JavaScript, commits, capturas ni URLs.

### Gestionar jugadores

La web permite anadir, editar y eliminar Riot IDs desde el boton de ajustes. La operacion requiere `MMRLOL_ADMIN_TOKEN`, que debe ser una cadena aleatoria larga y distinta de la clave de Riot.

```env
MMRLOL_ADMIN_TOKEN=un-secreto-largo-y-aleatorio
```

Cuando Riot esta configurado, los Riot IDs se validan antes de guardarlos. La configuracion se conserva en `MMRLOL_DATA_DIR` si esa variable esta definida.

### Despliegue

El repositorio incluye `Dockerfile` y `render.yaml`. El despliegue necesita estos secretos en el proveedor:

- `RIOT_API_KEY`
- `MMRLOL_ADMIN_TOKEN`
- `RIOT_VERIFICATION_TEXT`, cuando Riot entregue el contenido de verificacion
- `ALLOWED_HOSTS`, con el dominio publico y el dominio asignado por el proveedor

La aplicacion expone `/api/health`, `/privacy`, `/terms` y `/riot.txt`. El borrador para registrar el producto esta en `docs/riot-production-application.md`.

## Discord y avatares

El proyecto puede empaquetar avatares de Discord dentro del ejecutable.

Para eso se usan:

- `userdc_id.json`: mapeo entre jugador y `discord_user_id`
- `.env`: credenciales para descargar los avatares durante el build

Ejemplo de `.env`:

```env
DISCORD_BOT_TOKEN=tu_bot_token
DISCORD_GUILD_ID=tu_guild_id
```

## Generar el ejecutable

El build se hace con:

```powershell
build_exe.bat
```

Ese script:

- crea o reutiliza `.venv`
- instala dependencias
- genera el icono de la app
- descarga los avatares de Discord
- limpia builds anteriores
- construye el ejecutable `onefile` con PyInstaller

El resultado queda en:

`dist\MMRlol.exe`

## Estructura del proyecto

```text
main.py
build_exe.bat
LoLScout.spec
userdc_id.json
src/
  lolscout/
    app.py
    config.py
    models.py
    scraping_client.py
    lolalytics.py
    ui/
      main_window.py
      theme.py
      img/
scripts/
  generate_app_icon.py
  fetch_discord_avatars.py
```

## Archivos principales

- `main.py`: punto de entrada
- `src/lolscout/app.py`: arranque de la app y carga de recursos
- `src/lolscout/config.py`: lectura y guardado de configuracion
- `src/lolscout/scraping_client.py`: cliente de scraping de perfiles y ranking
- `src/lolscout/lolalytics.py`: cliente y parser de builds
- `src/lolscout/ui/main_window.py`: interfaz principal
- `src/lolscout/ui/theme.py`: estilos globales
- `build_exe.bat`: pipeline de build
- `LoLScout.spec`: empaquetado de PyInstaller

## Limitaciones conocidas

- depende de servicios externos y de su HTML/API publica
- algunos calculos publicos pueden variar si una fuente tarda en refrescar
- los enlaces de partida en vivo dependen de los datos publicos disponibles
- el build actual espera credenciales de Discord si quieres empaquetar avatares

## Uso rapido

1. Abre la app.
2. Configura jugadores y plataforma.
3. Actualiza **Hoy** para calcular el balance diario.
4. Actualiza **Ranking** para refrescar elo, LP y MMR.
5. Consulta **Builds** y **En partida** segun necesites.

## Objetivo del proyecto

Esta app no busca ser una copia de OP.GG ni de Lolalytics. La idea es concentrar en una sola herramienta privada lo importante para un grupo concreto:

- seguimiento diario de LP
- comparacion entre miembros del grupo
- scouting visual
- builds rapidas
- live tracking

## Licencia

Repositorio sin licencia publica declarada por ahora.
