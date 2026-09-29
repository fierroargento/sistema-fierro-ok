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
