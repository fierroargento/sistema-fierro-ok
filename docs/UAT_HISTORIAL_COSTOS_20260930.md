# UAT: acceso al historial de costos

Rama: integracion-saas-2026-09. Base oficial: 014b7708bdeaf123598eed8e1694a5692c9e6f98.

Costos base ofrece Gestionar en todas las filas, incluso la vigente. La ficha ofrece Ver costos e historial. Ambos abren el mismo popup y endpoint GET, restringido por organización, unidad activa y producto. Se leen CostoProductoVersion y sus detalles guardados; no se recalcula, activa ni edita ningún snapshot. Las acciones de activación existentes conservan su comportamiento.

El aviso de carga manual explica su requisito real: inclusión activa en catálogo. Ese requisito no se aplica al cálculo de una ficha técnica. No se activa ninguna inclusión automáticamente ni se modifican validaciones de negocio.

Validación: 23 tests de historial, panel comercial y gestión de máquinas; cuatro plantillas compiladas; Python y JS verificados. DOM: apertura, cierre, retorno de foco, ausencia de versiones y sesión vencida; solo GET, cero envíos de formularios. No se verificó visualmente en navegador real el popup nuevo.

## Próximo bloque de staging

- Abrir Gestionar de UAT-PROD-001: comprobar v1 vigente, ARS 4.932,25 y desglose original.
- Cerrar con X, Cerrar y Escape: sin modificaciones y conservando ubicación.
- Abrir el mismo historial desde la ficha técnica y comprobar igualdad.
- Después de validar estos accesos, retomar nueva versión de costo con tarifa de máquina v2 y aprobación separada.

Pendientes conservados: revisión visual del popup en staging y pantalla pequeña; comprobante adjunto de pago; revisión de formularios colapsados y alineación en pantallas aún no vistas. La barra lateral fue validada por el usuario y no es pendiente. Producción, integraciones y estados de pedidos quedan fuera de este cambio.
