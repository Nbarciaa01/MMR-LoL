# Solicitud de Production API Key para SoloQ Scout

Texto preparado para **Register Product** en Riot Developer Portal. Antes de enviarlo solo faltan los dos datos marcados como `PENDIENTE` y el texto de verificacion que Riot entregue durante el proceso.

## Nombre del producto

SoloQ Scout

## URL

`https://mmrlol-web.onrender.com/`

## Descripcion corta

SoloQ Scout es una dashboard comunitaria que permite consultar la clasificacion oficial de SoloQ, el cambio diario de LP, las partidas recientes y el estado en partida de un grupo de jugadores de League of Legends.

## Descripcion detallada

La aplicacion permite configurar hasta 25 Riot IDs de un grupo. Para cada cuenta muestra su rango y LP oficiales de SoloQ, victorias, derrotas, porcentaje de victorias y partidas clasificatorias. Match-V5 se utiliza para obtener las partidas de SoloQ jugadas desde las 00:00 de la zona horaria configurada y presentar el resultado, campeon y estadisticas basicas. Spectator-V5 se utiliza para indicar si un jugador esta en partida y mostrar la composicion disponible.

Los cambios diarios de LP se calculan comparando la clasificacion oficial actual con snapshots propios guardados por la aplicacion. SoloQ Scout no calcula, muestra ni ofrece un MMR alternativo. El ranking del grupo se ordena por tier, division y LP oficiales.

La web es accesible publicamente en modo lectura. Las funciones para anadir, editar o eliminar Riot IDs estan protegidas por un token administrativo que permanece en el servidor.

## APIs solicitadas

- ACCOUNT-V1: resolver Riot ID y PUUID.
- SUMMONER-V4: obtener nivel, icono y summoner ID.
- LEAGUE-V4: obtener clasificacion oficial SoloQ y Flex.
- MATCH-V5: consultar historial y detalle de partidas SoloQ del dia.
- SPECTATOR-V5: consultar estado y participantes de partidas activas.

## Seguridad y limites

- La API key solo existe como secreto del servidor y nunca se incluye en HTML o JavaScript.
- Las identidades se cachean durante 6 horas.
- La clasificacion y su respuesta publica se cachean durante 90 segundos.
- Las listas de partidas se cachean durante 60 segundos.
- Los detalles de partidas terminadas se cachean durante 24 horas.
- Spectator-V5 se cachea durante 20 segundos.
- El resumen de Hoy se cachea durante 45 segundos y En partida durante 15 segundos.
- Los snapshots diarios se guardan en PostgreSQL y usan la zona `Europe/Madrid`.
- Los errores 429 respetan `Retry-After`; el navegador no realiza reintentos agresivos.
- La gestion de jugadores requiere un secreto administrativo independiente.

## Enlaces requeridos

- Producto: `https://mmrlol-web.onrender.com/`
- Privacidad: `https://mmrlol-web.onrender.com/privacy`
- Terminos: `https://mmrlol-web.onrender.com/terms`
- Verificacion: `https://mmrlol-web.onrender.com/riot.txt`
- Repositorio: `https://github.com/Nbarciaa01/MMR-LoL`

## Monetizacion

El producto no tiene monetizacion, publicidad, compras ni suscripciones.

## Contacto

- Responsable: `PENDIENTE: nombre legal del responsable`
- Correo publico: `PENDIENTE: correo de contacto`
- Pais: Espana

## Texto legal de Riot

SoloQ Scout isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc.

## Lista previa al envio

- Completar el nombre legal y el correo publico de contacto.
- Generar una development key vigente para que Riot pueda probar la aplicacion mientras revisa la solicitud.
- Iniciar **Register Product** y copiar los textos de este documento.
- Cuando Riot entregue el texto de verificacion, guardarlo sin cambios en `RIOT_VERIFICATION_TEXT` dentro de Render.
- Desplegar de nuevo y comprobar que `/riot.txt` devuelve exactamente ese texto.
- Enviar la solicitud de production key.
- Al aprobarse, sustituir `RIOT_API_KEY` en Render por la production key y desplegar.
