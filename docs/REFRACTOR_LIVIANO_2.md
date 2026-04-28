# Sistema Fierro - Refactor liviano 2

Base tomada como ancla: `sistema_fierro_refactor_liviano_1.zip`.

## Criterio aplicado

Se priorizo no romper lo validado:

- ML funcionando.
- Tienda Nube funcionando con sync/webhooks.
- Seguridad aplicada.
- Auditoria aplicada.
- Detalle TN OK.
- Link TN OK.
- Re-sync TNube como boton.
- Tracking TN 319 ya resuelto previamente: no se modifica la logica runtime.

## Cambios incluidos

1. `services/tiendanube_helpers.py` queda mas completo como modulo puro preparatorio.
   - Sin Flask.
   - Sin base de datos.
   - Sin llamadas HTTP.
   - Sin efectos secundarios.
   - Incluye reglas puras de pago, cancelacion, enviado y extraccion defensiva de tracking.

2. `app.py`
   - Solo limpieza de comentario/docstring duplicado en `tn_extraer_tracking`.
   - No cambia comportamiento operativo.

## Importante

Este ZIP es deployable completo, pero el refactor sigue siendo conservador:
la app continua usando la logica validada de `app.py`. La separacion real se deja preparada para migrar en bloques chicos y testeables.
