# Solicitud de Production API Key para MMR LoL

Este documento es un borrador para completar **Register Product** en el Riot Developer Portal. Sustituye los campos entre corchetes antes de enviarlo.

## Nombre del producto

MMR LoL

## URL

`https://[dominio-publico]`

## Descripcion corta

MMR LoL es una dashboard comunitaria para consultar en un solo lugar la clasificacion, el cambio diario de LP, las partidas activas y builds de un grupo de jugadores de League of Legends.

## Descripcion detallada

La aplicacion permite configurar hasta 25 Riot IDs de un grupo. Para cada cuenta muestra el rango de SoloQ, LP, victorias, derrotas y una estimacion visual de MMR. Match-V5 se utiliza para obtener las partidas de SoloQ jugadas desde las 00:00 locales y mostrar resultados y estadisticas basicas. Spectator-V5 se utiliza para indicar si un jugador esta en partida y mostrar la composicion disponible.

Los cambios de LP se calculan comparando la clasificacion actual con snapshots propios guardados por la aplicacion. La estimacion de MMR no es un dato oficial de Riot y se identifica como estimacion en la interfaz.

La aplicacion esta pensada inicialmente para una comunidad pequena de amigos, pero la web sera accesible publicamente. Las funciones de edicion estan protegidas por un token de administracion. Los visitantes solo pueden consultar los datos configurados.

## APIs solicitadas

- ACCOUNT-V1: resolver Riot ID y PUUID.
- SUMMONER-V4: nivel, icono y summoner ID.
- LEAGUE-V4: clasificacion SoloQ y Flex.
- MATCH-V5: historial y detalle de partidas SoloQ del dia.
- SPECTATOR-V5: estado y participantes de partidas activas.

## Seguridad y limites

- La API key solo existe como secreto del servidor y nunca se incluye en HTML o JavaScript.
- Las identidades se cachean durante 6 horas.
- La clasificacion se cachea durante 90 segundos.
- Las listas de partidas se cachean durante 60 segundos.
- Los detalles de partidas terminadas se cachean durante 24 horas.
- Spectator-V5 se cachea durante 20 segundos.
- Los errores 429 se respetan usando `Retry-After` y se muestran sin reintentos agresivos desde el navegador.
- La gestion de jugadores requiere un secreto administrativo independiente.

## Enlaces requeridos

- Producto: `https://[dominio-publico]/`
- Privacidad: `https://[dominio-publico]/privacy`
- Terminos: `https://[dominio-publico]/terms`
- Verificacion: `https://[dominio-publico]/riot.txt`
- Repositorio: `[URL del repositorio, si sera publico]`

## Monetizacion

El prototipo no tiene monetizacion, publicidad, compras ni suscripciones.

## Contacto

- Responsable: `[nombre completo]`
- Correo: `[correo de contacto]`
- Pais: Espana

## Revision previa al envio

- La production key no debe solicitarse hasta que la URL publica funcione.
- `riot.txt` debe mostrar exactamente el texto de verificacion entregado por Riot.
- El dominio debe servir HTTPS.
- La politica de privacidad debe incluir un medio de contacto real.
- Deben eliminarse o completarse todos los campos entre corchetes.
