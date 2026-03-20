# MMR LoL

Aplicacion de escritorio para Windows orientada a seguir un grupo cerrado de jugadores de League of Legends desde una sola interfaz.

La app combina varias fuentes externas para mostrar:

- balance diario de LP en SoloQ
- ranking del grupo por elo y MMR estimado
- builds y matchups desde Lolalytics
- partidas activas en vivo
- galeria visual de jugadores
- enlaces rapidos y soporte para spectate

El proyecto esta construido con `Python` + `PySide6` y se distribuye como ejecutable autosuficiente `MMRlol.exe`.

## Que hace la app

### 1. Hoy

La pestana **Hoy** calcula el balance diario de LP de los jugadores configurados.

Incluye:

- LP netos del dia
- rango actual
- ultimas partidas jugadas hoy
- deteccion de partidas de **SoloQ** desde las `00:00` locales

La logica usa snapshots locales y, cuando hay API de Riot disponible, prioriza Riot para mejorar la precision del calculo.

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

Si la configuracion esta completa, la app tambien puede lanzar el modo **spectate**.

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

- `Riot API`: identidad de cuenta, ranked mas fiable, live game, spectate y parte del calculo diario
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

## Configuracion

La app guarda su configuracion en:

`%APPDATA%\LoLScout\config.json`

Entre otras cosas se almacenan:

- plataforma por defecto
- jugadores del grupo
- API Key de Riot
- ruta local de League of Legends para spectate

## Riot API: cuando hace falta

La app puede funcionar parcialmente sin API Key, pero no con la misma precision.

### Sin Riot API

Siguen funcionando o pueden funcionar:

- ranking basico
- builds
- parte del scouting visual
- consulta publica de perfiles

### Con Riot API

Mejora o habilita:

- mayor precision en la pestana **Hoy**
- live game mas fiable
- spectate
- deteccion de maestria y algunos detalles adicionales

En la practica, si quieres usar la app "al 100%", conviene configurar una API Key valida.

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
    riot_api.py
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
- `src/lolscout/riot_api.py`: integracion con Riot y scraping auxiliar
- `src/lolscout/lolalytics.py`: cliente y parser de builds
- `src/lolscout/ui/main_window.py`: interfaz principal
- `src/lolscout/ui/theme.py`: estilos globales
- `build_exe.bat`: pipeline de build
- `LoLScout.spec`: empaquetado de PyInstaller

## Limitaciones conocidas

- depende de servicios externos y de su HTML/API publica
- algunos calculos publicos pueden variar si una fuente tarda en refrescar
- el modo spectate requiere API Key y ruta valida de League
- el build actual espera credenciales de Discord si quieres empaquetar avatares

## Uso rapido

1. Abre la app.
2. Configura jugadores, plataforma y, si la tienes, API Key de Riot.
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
