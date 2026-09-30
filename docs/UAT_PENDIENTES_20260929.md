# Correcciones del bloque UAT comercial y proveedores

Base oficial: 407cbff18318b597ff7603600b0dc57b5b33e131, rama integracion-saas-2026-09.
Producción main queda fuera de alcance. Sin llamadas a canales, scheduler ni cambios de estados de pedidos.

## Implementado para validar en staging

- Cola: las propuestas obsoletas muestran Obsoleta y solo ofrecen archivo con motivo. El servidor permite archivar una aprobada obsoleta, mantiene el bloqueo de aprobar/completar y conserva snapshot, huella y auditoría. Las dependencias pendientes ocultan la confirmación manual. Orden por cadena y secuencia, vigentes antes que obsoletas.
- Excel: precio base de la promoción activa o del último precio importado; NO_OBSERVADA cuando no existe observación de promoción, NO cuando se observó inactiva.
- Formularios: carga comercial y fuentes colapsadas por defecto. Las cuatro importaciones de canal cierran el mapeo tras validar y confirmar y permiten reabrirlo. Confirmación por popup sin frase escrita.
- Presentación: botones compactos, casillas nativas, tablas contenidas, porcentajes con hasta dos decimales, motivos y vigencias con nombres legibles. Se conserva posición al volver de un POST dentro de la sección de trabajo.
- Reglas económicas: selector preparatorio incluye productos borrador y error de selección legible. No se cambian los controles de activación/publicación.
- Proveedor: ampliación del maestro ProveedorCompra con domicilio, localidad, provincia, código postal y persona de contacto. Crear, editar, detalle e importación reutilizan el maestro y su validador. Edición limitada a organización activa; código conserva identidad. Campos omitidos en planillas viejas preservan valores existentes.
- Migración aditiva e idempotente al inicio, cinco columnas nullable, sin backfill ni otro maestro fiscal.

## Validación realizada

53 pruebas de cola, control, vigencias, proveedores, Compras, templates y bootstrap; compilación Python/Jinja; sintaxis JavaScript. Migración SQLite ejecutada dos veces: cinco columnas en la primera, cero en la segunda, fila existente intacta.

## Próxima UAT

1. Tras deploy, la cola UAT actual debe mostrar tres obsoletas sin Confirmar gestión manual. Archivar una con motivo ficticio y verificar reducción del contador y conservación del registro.
2. Exportar control: UAT-PROD-001 rentable, base y efectivo 7125, neto 6412.50, promoción NO, sin_accion.
3. Revisar formularios colapsados, mapeo reabrible, botones/tablas/checkboxes y continuidad de scroll.
4. Editar UAT-PROV-001 con domicilio y contacto ficticios, guardar y abrir detalle. Reimportar una plantilla antigua sin esas columnas y confirmar que conserva esos datos y no duplica proveedor.

La validación visual y PostgreSQL del deploy queda pendiente de UAT en staging. No confirmar gestiones manuales externas que no se realizaron. Barra lateral ya validada, no se altera su integración.


## Bloque preparado el 30/09: gestión y presentación

Base oficial b89140c806fb4fbcb0b070332b7da59ac54ea613. Cambios locales, pendientes de deploy y validación visual en staging.

- Proveedores y editores de Compras abren emergentes reutilizando los formularios y validadores existentes. Cancelar cierra sin guardar; se conserva Cerrar y Escape.
- Máquinas incorporan Gestionar, precarga de tarifa vigente e historial. Guardar usa la actualización existente que crea una nueva versión. Identidad y estado interno se validan dentro del ámbito de organización/unidad.
- Formularios generales colapsados; botones compactos con altura, colores y alineación comunes. Diálogos con encabezado separado de la X, acciones agrupadas y adaptación a pantallas pequeñas.
- Compras reutiliza la restauración de posición compartida; se elimina el manejador duplicado.
- Vencimientos ordenados de más próximo a más lejano. Calendarios conservan la frecuencia seleccionada y aclaran que la anticipación se expresa en meses. Fechas de historial de importación de proveedores en hora argentina.

UAT siguiente: abrir/cancelar proveedor sin cambios; gestionar UAT-MAQ-001 y verificar historial y aislamiento; comprobar pago parcial y anulado conservados; verificar vencimientos de octubre antes de noviembre, frecuencia persistida y ausencia de duplicados; revisar diálogos y botones en escritorio y móvil.

La barra lateral ya está validada. No se modifican producción, integraciones, scheduler ni estados de pedidos. La cobertura visual de fichas técnicas y otros formularios no incluidos aquí sigue pendiente de revisión; no se da por resuelta por estas reglas compartidas.

Validación local del bloque: 57 pruebas de gestión, aislamiento, tarifas, cuentas a pagar y Compras; sintaxis JavaScript y compilación Python/Jinja correctas. El navegador de pruebas no pudo instalarse en este entorno; no se afirma validación visual ni deploy.
