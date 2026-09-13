# Revision de MMRQ Challenge

## Cambios implementados

- Logo original MMR y favicon restaurados. Es el emblema del grupo, no una afirmacion de respaldo de Riot.
- Ranking oficial por tier, division y LP. El cliente Riot no calcula MMR.
- Web sin fallback de scraping, incluido el historial de LP de OP.GG.
- Claves de cache nuevas para no reutilizar respuestas antiguas de otras fuentes.
- Data Dragon para catalogo e iconos. Builds abre Lolalytics mediante enlaces externos.
- Spectator utiliza solo nombres visibles en su respuesta, sin resolver identidades ocultas.
- Token de Riot enviado solo mediante HTTPS a hosts de su API, sin seguir redirecciones.
- Acceso privado separado de la administracion y sin cache publica de datos privados.
- Aviso legal de Riot visible. Sin pagos, premios, apuestas ni etiquetas despectivas.

## Configuracion antes del despliegue en Render

Configurar estos valores en Environment antes de desplegar:

- MMRLOL_ACCESS_MODE=prototype
- RIOT_KEY_TYPE=development
- MMRLOL_VIEWER_USER=mmr
- MMRLOL_VIEWER_PASSWORD: una contrasena larga y distinta de MMRLOL_ADMIN_TOKEN.

El navegador pedira usuario y contrasena. El token de administracion sigue siendo necesario para editar jugadores. Nunca compartir la clave Riot con los visitantes.

Sin contrasena, Render bloquea el panel y los endpoints de datos con 503. Health, paginas legales, recursos estaticos y riot.txt quedan disponibles para operacion y revision. El desarrollo local directo permite acceso sin contrasena.

Con personal key aprobada: RIOT_KEY_TYPE=personal y MMRLOL_ACCESS_MODE=private. Compartir el acceso solo con el grupo.

Para abrir al publico: obtener production key y establecer RIOT_KEY_TYPE=production y MMRLOL_ACCESS_MODE=public. La aplicacion no puede identificar el tipo de clave por su texto; esta declaracion debe coincidir con la clave realmente concedida por Riot.

## Pendiente de decisiones externas

- Registrar el proyecto y obtener la clave adecuada; una development key solo sirve para el prototipo.
- Confirmar con Riot mediante App Note el emblema y su parecido estilizado con escudos de rango.
- Completar responsable y contacto real antes de publicar una politica de privacidad definitiva.
- Aceptar personalmente los terminos del Developer Portal.
- Revisar visualmente el despliegue. Estos cambios no constituyen una aprobacion de Riot.

El codigo de escritorio heredado conserva integraciones antiguas. Esta revision cubre la web; no declarar el ejecutable como aprobado ni distribuirlo basandose en esta revision.
