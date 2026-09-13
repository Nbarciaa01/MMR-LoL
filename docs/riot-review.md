# Revision de MMRQ Challenge

## Cambios implementados

- Logo original MMR y favicon restaurados. Es el emblema del grupo, no una afirmacion de respaldo de Riot.
- Ranking oficial por tier, division y LP. El cliente Riot no calcula MMR.
- Web sin fallback de scraping, incluido el historial de LP de OP.GG.
- Claves de cache nuevas para no reutilizar respuestas antiguas de otras fuentes.
- Data Dragon para catalogo e iconos. Builds abre Lolalytics mediante enlaces externos.
- Spectator utiliza solo nombres visibles en su respuesta, sin resolver identidades ocultas.
- Token de Riot enviado solo mediante HTTPS a hosts de su API, sin seguir redirecciones.
- Consulta abierta sin registro ni contrasena; edicion protegida por token de administracion.
- Aviso legal de Riot visible. Sin pagos, premios, apuestas ni etiquetas despectivas.

## Configuracion antes del despliegue en Render

El panel y los endpoints de consulta son accesibles sin credenciales para cualquiera con el enlace. Solo la edicion de jugadores requiere MMRLOL_ADMIN_TOKEN.

Las variables MMRLOL_ACCESS_MODE, MMRLOL_VIEWER_USER, MMRLOL_VIEWER_PASSWORD y RIOT_KEY_TYPE ya no se utilizan. Si siguen en Render, no bloquean el acceso y se pueden eliminar. Desplegar el ultimo commit para aplicar el cambio.

La clave de Riot sigue siendo un secreto del servidor. La solicitud del producto debe reflejar que la consulta esta abierta al publico.

## Pendiente de decisiones externas

- Registrar el proyecto y obtener la clave adecuada; una development key solo sirve para el prototipo.
- Confirmar con Riot mediante App Note el emblema y su parecido estilizado con escudos de rango.
- Completar responsable y contacto real antes de publicar una politica de privacidad definitiva.
- Aceptar personalmente los terminos del Developer Portal.
- Revisar visualmente el despliegue. Estos cambios no constituyen una aprobacion de Riot.

El codigo de escritorio heredado conserva integraciones antiguas. Esta revision cubre la web; no declarar el ejecutable como aprobado ni distribuirlo basandose en esta revision.
