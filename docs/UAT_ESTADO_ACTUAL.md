# Estado único de UAT — staging
Fecha de corte: 15/10/2026, Argentina.
Rama: `integracion-saas-2026-09`.
Base de código revisada: `379b6f6a86b80742064efbdc77706d979a526670`.

Este documento concentra el seguimiento desde esta fecha. Los documentos UAT de septiembre conservan su valor histórico; sus frases «pendiente de deploy» o «pendiente de validación» no prueban que el pendiente siga abierto hoy.

## Alcance y criterio de cierre

- Trabajo exclusivo en staging, con datos sintéticos y laboratorio desconectado.
- Producción, main, credenciales y activaciones externas quedan fuera de este cierre.
- Se mantienen `BOOTSTRAP_BASE_DATOS_HABILITADO=false` y `MODO_LABORATORIO_DESCONECTADO=true`.
- Un control de integridad aprobado no equivale a aceptación funcional completa ni habilita un piloto real.
- No repetir pruebas aprobadas salvo cambio relevante, regresión o evidencia contradictoria.
- Registrar cada nueva prueba con pantalla exacta, acción, resultado y evidencia. No crear un segundo registro de pendientes.

## Cerrado con evidencia reciente

| Área | Resultado y evidencia |
| --- | --- |
| Estructura | Control integral aprobado, sin hallazgos. |
| Accesos | Certificación aprobada, sin hallazgos. |
| Inventario | Certificación integral aprobada, sin hallazgos. |
| Facturación offline | Certificación aprobada; cinco borradores cancelados. |
| CRM manual | Etapa, cliente, identidad, oportunidad y actividad sintéticos probados; cancelación, cambios de estado y rechazo de identidad duplicada aceptados durante UAT. |
| Importación CRM | Tres filas previsualizadas; lote #1 confirmado una vez; repetición rechazada; anulación conserva los registros; repetir el archivo después de anular también se rechaza. |
| Evidencia de lote | `lote_crm_1 (1).json`: estado anulado; el único campo distinto del original es estado; evidencia interna idéntica y huella válida. |
| Certificación CRM posterior | `certificacion_crm_offline (3).json`: aprobada, cero hallazgos; clientes 2, oportunidades 2, actividades 2, identidades 1, etapas 1, unidades 2. CRM desactivado. |
| Consolidación | `expediente_consolidado_saas (4).json`: cinco componentes aprobados, cero faltantes/hallazgos, huella verificada e informe CRM más reciente incluido. |
| Control integral CRM | `control_integral_crm.json`: aprobado, huella válida, cero hallazgos de CRM y cero inconsistencias de lotes; un lote anulado y cero confirmados. |
| Visual de control CRM | Commit `6c16ca9c329290dd9ddc36d77d806e151ce26779`; usuario respondió «perfecto» tras entrega. No se afirma inspección automatizada del navegador de Render. |

Huella del consolidado: `b18bbd0d6f81f00d424f37c0c9d6ce7de294cd9bfbdb885fcc7db6cec5dcc52d`.

## Bloque 1 — cerrar la última corrección CRM

- [ ] Confirmar deploy en staging de `379b6f6a86b80742064efbdc77706d979a526670`.
- [ ] Una prueba negativa de CSV con importe no representable: la oportunidad debe aparecer rechazada con aviso, la pantalla debe responder normalmente y no debe crearse ningún lote.
- [ ] Marcar el bloque cerrado con esa evidencia. No volver a ejecutar el circuito completo de importación/anulación ni descargar otra vez los cinco controles por este cambio aislado.

Ya verificado localmente: 26 pruebas de previsualización y confirmación aprobadas. Casos no representables NaN, sNaN, Infinity, -Infinity y exponente excesivo se rechazan por fila; importes válidos conservan su conversión y redondeo. Se comprobaron además rechazos de importe alterado sin huella actualizada, plan de otra organización, unidad ajena aun con huella recalculada y archivo repetido de lote anulado. Son verificaciones locales, no pruebas ejecutadas contra la base de staging.

## Bloque 2 — reconciliar pendientes históricos y cubrir cruces

Antes de solicitar pruebas al usuario, contrastar el código actual y las evidencias existentes. Estas filas son tareas de conciliación; no se declaran defectos actuales.

| Grupo | Qué resolver | Criterio de cierre |
| --- | --- | --- |
| Presentación | Mapeo colapsado/reabrible, formularios cerrados, tamaños/colores/orden de botones, tablas, avisos y emergentes. Revisar especialmente pantallas aún sin evidencia. | Registrar qué fue aceptado y abrir únicamente los defectos que subsistan. No reabrir la barra lateral ya aceptada. |
| Navegación y cancelación | Continuidad de scroll, Volver, accesos, Gestionar y cierre sin guardar por Cancelar/X/Escape. | Reutilizar las confirmaciones previas; probar solo rutas modificadas o no verificadas. |
| Comercial y costos | Historial, simulador de canal, modificación de precios, acceso a archivos; mantener visibles las acciones existentes. | Reconciliar los antiguos avisos de opciones faltantes con el código y las correcciones posteriores. |
| Compras, proveedores y pagos | Datos fiscales/contacto, compatibilidad de importaciones antiguas, conciliación y pagos/vencimientos. | Conservar pruebas aprobadas; identificar si falta un cruce concreto, sin generar obligaciones reales. |
| Flujos entre módulos | Producto/costo/propuesta; compra/recepción/factura/propuesta; obligación/pago/anulación, solo donde el modo preparatorio lo permita. | Definir un caso sintético por cruce que aún no tenga evidencia suficiente. No repetir altas aisladas ya aprobadas. |

Fuentes históricas: `docs/UAT_PENDIENTES_20260929.md`, `docs/UAT_COMPRAS_20260929.md` y `docs/UAT_HISTORIAL_COSTOS_20260930.md`. La aceptación posterior del usuario tiene prioridad sobre un «pendiente» antiguo. Si no puede asociarse con certeza una confirmación a un caso, queda «por conciliar», no aprobado ni fallado.

## Bloque 3 — aceptación final de staging

- [ ] Completar la conciliación del bloque 2 y resolver defectos confirmados.
- [ ] Revisar cobertura de aceptación por usuarios/roles ya existente antes de pedir otra ronda.
- [ ] Ejecutar regresión focalizada sobre lo que cambió y sobre los cruces pendientes.
- [ ] Verificar readiness del commit final y barreras de staging, sin activar conexiones.
- [ ] Consolidar evidencia final solo de componentes afectados y dejar un acta de alcance y limitaciones.
- [ ] Registrar los requisitos de un futuro piloto real en una etapa separada; no confundir este cierre con habilitación productiva.

La documentación de remediación de septiembre cita riesgos pendientes de canales, selección ML por organización, proxy, archivos y tokens. Su estado actual debe contrastarse con el código antes de afirmar que siguen abiertos o que están resueltos; no están acreditados por los cinco informes de integridad actuales.

## Estimación y siguiente acción

Hay tres bloques de cierre definidos; el primero es breve. El esfuerzo de los otros dos depende de la conciliación y de los defectos que efectivamente subsistan. No se asigna un porcentaje de SaaS terminado ni un plazo de producción sin ese inventario.

Siguiente acción concreta: deploy de `379b6f6a86b80742064efbdc77706d979a526670` y una única prueba negativa del bloque 1. Este documento por sí solo no requiere deploy.
