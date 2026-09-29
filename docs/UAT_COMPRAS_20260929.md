# UAT de staging · 29/09/2026

Rama: integracion-saas-2026-09. Producción main@9b63fe6 fuera de alcance.

## Evidencia funcional

Proveedor UAT-PROV-001 importado una sola vez. Reimportación: sin cambios.
Orden UAT-OC-001: 2 kg a $1500, total $3000. Borrador → revisión → devolución → borrador → revisión → aprobada.
Recepción parcial UAT-REC-001: 1 kg, $1500, preparatoria.
Factura A 00001-00900001: conciliada, diferencia $0.
Tres propuestas; repetir preparación no duplica: costo aprobada, cuenta a pagar rechazada con motivo «Prueba UAT sin obligación real», stock bloqueada sin mapeo. Ejecución bloqueada en las tres.
Exportación original: 1 orden, 1 recepción, 1 factura y 3 propuestas, sin hallazgos. Sus ceros de impactos eran constantes, no mediciones independientes.

## Correcciones para reverificar en staging

- Cancelar visible y cierre de ficha descartan campos, filas dinámicas y vista previa; reabrir debe mostrar lo guardado.
- Formularios de Compras colapsados, editores de orden/recepción en filas completas, campos etiquetados y botones compactos.
- Ver detalle del proveedor: email, teléfono y observación.
- Continuación tras guardar en el bloque de destino con el mensaje visible.
- Cantidades sin ceros redundantes y estados legibles.
- Clasificación de productos: confirmar mediante botón y diálogo, sin frase literal; validaciones del servidor conservadas.
- Control exportado incluye trazabilidad y separa indicadores de registros de impactos no medidos (null).

## Límites y pendientes

Reverificar visualmente en Render antes de cerrar estos hallazgos. No activar canales reales ni aplicar impactos.
El control sigue sin consultar movimientos de inventario, versiones efectivas de costos, obligaciones contables ni conexiones externas; su aprobado se limita a consistencia preparatoria.
Revisar formularios de otros módulos durante sus respectivos bloques UAT; el colapso de este cambio se limita a Compras.
