# Consulta de CUIT en maestros de clientes y proveedores

La opción **Consultar ARCA** prepara datos para el formulario; no crea el registro, no activa clientes ni habilita facturación. La consulta obtiene nombre o razón social y domicilio fiscal (dirección, localidad, provincia, código postal). El usuario revisa y pulsa **Usar estos datos**. Por defecto se conservan los campos ya escritos; reemplazarlos requiere marcar la opción del resultado. Consultar, descartar y cancelar no envían el alta. Cambiar CUIT o cancelar invalida cualquier respuesta pendiente.

Email, teléfono general, persona de contacto y teléfono de esa persona son datos manuales. El padrón no se usa para inventarlos. El domicilio fiscal de clientes no modifica direcciones de pedidos ni de envíos.

## Estado de esta entrega

Implementación para integración/staging, probada con respuestas sintéticas y red simulada. No se activaron consultas reales, credenciales ni autorizaciones externas. Se reutilizan EntidadFiscal y ConfiguracionFiscal existentes; no se crea un segundo maestro de personas ni de proveedores. Las tablas nuevas son extensiones uno a uno: domicilio/código postal de clientes y teléfono del contacto de proveedores.

El acceso requiere administrador del tenant resuelto por los blueprints existentes. El CUIT representado se selecciona expresamente por organización y se verifica contra EntidadFiscal y ConfiguracionFiscal de esa misma organización; no se toma el primer CUIT disponible. POST y protección CSRF global existentes. Respuesta JSON sin caché; no se expone el SOAP ni tickets al navegador.

## Preparación de campos en staging

Después de desplegar, ejecutar una vez en el Shell del servicio de staging:

```sh
python -m scripts.preparar_maestros_contacto --staging
```

El comando exige laboratorio desconectado, RENDER_GIT_BRANCH de integración y URL de servicio de staging. Crea únicamente las dos tablas complementarias, es idempotente y no modifica registros existentes. Sin preparación, listados y altas antiguas siguen funcionando; los campos nuevos quedan deshabilitados con aviso, y el servidor rechaza un intento de guardar esos campos sin su tabla. No cambiar los flags del laboratorio.

## Autorización para una futura consulta real (fuera de esta UAT)

ARCA utiliza el servicio **ws_sr_constancia_inscripcion**, método **getPersona_v2**, con token y sign obtenidos mediante WSAA. El acceso requiere la autorización del servicio para el CUIT representado.

La implementación consume un **loginTicketResponse XML vigente de WSAA** para ese servicio, mediante la variable cuyo nombre ya guarda ConfiguracionFiscal.token_env. No recibe tickets desde el navegador ni modifica la configuración fiscal. La obtención y renovación automática de tickets/certificados no está incluida en esta entrega: deberá resolverse antes de considerarla una integración productiva desatendida. No reutilizar un ticket de otro servicio ni cambiar referencias utilizadas por facturación sin revisar su configuración.

La selección explícita se realiza mediante ARCA_PADRON_ENTIDAD_<organizacion_id>, cuyo valor es el ID de la entidad fiscal. ConfiguracionFiscal debe corresponder a esa entidad y organización, proveedor arca y ambiente homologacion o produccion. Los únicos endpoints admitidos son los oficiales fijados en código:

- Homologación: https://awshomo.arca.gov.ar/sr-padron/webservices/personaServiceA5
- Producción: https://aws.arca.gov.ar/sr-padron/webservices/personaServiceA5

El adaptador solo sale a red cuando la frontera central autoriza ARCA: entorno explícito válido, CONEXIONES_EXTERNAS_HABILITADAS y ARCA_CONEXION_HABILITADA. MODO_LABORATORIO_DESCONECTADO prevalece siempre y bloquea antes de leer credenciales o consultar. Esta entrega no cambia ninguna de esas variables, no pide habilitar facturación ni emite comprobantes. No cargar certificados, claves o tickets en Git ni compartirlos por chat.

## UAT segura

1. Preparar campos y recargar con Ctrl+F5. En Base de Datos / Proveedores, verificar teléfono general y teléfono de la persona de contacto separados al crear, gestionar y editar. Cancelar debe descartar el cambio; guardar debe conservarlo al recargar.
2. En Base de Datos / Clientes, guardar un registro UAT con domicilio/código postal y comprobarlos en Ver datos. El cliente conserva el comportamiento actual de crearse desactivado.
3. En ambas altas, Consultar ARCA con CUIT válido debe mostrar la consulta bloqueada en este entorno; no debe alterar datos ni crear registros. Con CUIT inválido debe mostrar aviso. La carga manual sigue disponible.
4. El éxito de consulta, aplicación, conservación de campos manuales, respuestas tardías y errores se verificó con mocks. La consulta real y la renovación de autorización quedan pendientes de una etapa expresamente conectada.

Fuentes oficiales consultadas el 20/10/2026:
- [Catálogo de servicios ARCA](https://www.arca.gob.ar/ws/documentacion/catalogo.asp)
- [Manual de constancia de inscripción, versión 3.5](https://www.afip.gob.ar/ws/WSCI/manual-ws-sr-ws-constancia-inscripcion.pdf)
