# Estado único de UAT — staging
Fecha de corte: 16/10/2026, Argentina.
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

- [x] Corrección de importes no representables verificada en la pantalla de staging el 16/10/2026. La captura no acredita por sí sola el SHA exacto de Render.
- [x] Prueba negativa con `uat_crm_importe_invalido.csv`: dos filas, una preparada y una rechazada, mensaje «Importe o probabilidad inválidos»; respuesta normal y únicamente el lote #1 anulado visible.
- [x] Bloque CRM cerrado con `image(20261016-130852).png`. No repetir el circuito de importación/anulación ni los cinco controles por este cambio aislado.

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

Siguiente acción concreta: verificar feedback de Simular escenario y alineación de Promoción vigente tras el deploy, sin persistir datos.

### Conciliación visual del 16/10/2026

- Costos base: tabla contenida y acciones presentes. Producto UAT-PROD-001 con v2 vigente $4.933,65 y v1 archivada $4.932,25. Evidencia `image(20261016-131010).png`.
- Historial del producto: emergente contenida, desglose legible, v2 desplegada y v1 plegada. Se cierra el pendiente visual del historial; evidencia `image(20261016-131109).png`.
- Fuentes de costo: captura general con formularios plegados, insuficiente resolución para cerrar todos los detalles de presentación; `image(20261016-153012).png`.
- Máquinas: Gestionar disponible, datos precargados e historial de dos tarifas visible y contenido. Evidencias `image(20261016-153141).png` y `image(20261016-153248).png`. No se vuelve a declarar ausente Gestionar ni el historial.
- MUI-01 cerrado: etiquetas y campos monetarios alineados en la captura posterior al ajuste, `image(20261016-160030).png`. Gestionar e historial de Máquinas visualmente verificados.
- Estas capturas no acreditan nuevas pruebas de guardado, cancelación o cálculo; sus pruebas funcionales anteriores no se repiten por este ajuste de presentación.

### Continuación del 16/10/2026: Pagos, Proveedores y cruce documental de Compras

- Pagos y vencimientos: tabla contenida, configuración plegada y botones uniformes; tres obligaciones visibles, dos vencidas. La parcial conserva $40.000 aplicados y $80.000 pendientes. Evidencia `image(20261016-160155).png`.
- Gestión de pago: tres movimientos, uno aplicado por $40.000 y dos anulados ($80.000 y $1.000); acceso Ver archivo presente. La captura verifica presentación y valores visibles, no una nueva descarga o anulación. Evidencia `image(20261016-160232).png`.
- Proveedor UAT-PROV-001: ficha con datos fiscales, contacto, domicilio y observaciones, y editor con campos alineados. Cerrados esos pendientes visuales. Evidencias `image(20261016-160357).png` y `image(20261016-160437).png`.
- Orden UAT-OC-001: aprobada, total $3.000; recepción parcial UAT-REC-001 por $1.500, preparatoria. Evidencias `image(20261016-160545).png` y `image(20261016-160650).png`.
- Factura A 00001-00900001: vinculada a UAT-REC-001, total $1.500, diferencia $0, conciliada. Evidencia `image(20261016-160803).png`.
- Tres propuestas de UAT-REC-001: cuenta a pagar rechazada con motivo «Prueba UAT sin obligación real»; stock bloqueado, requiere mapeo de inventario; costo aprobado. Las tres muestran ejecución bloqueada. Evidencia `image(20261016-160839).png`.
- Queda conciliado el estado visible del cruce documental existente orden → recepción → factura → propuestas. No se crearon nuevas recepciones/facturas ni se repitieron aprobaciones, y estas capturas no miden impactos en otros módulos.
- CH-01 cerrado con `image(20261016-163634).png`: subtítulo separado y legible. Antecedente: el subtítulo de Gestionar orden concatenaba número, cantidad de ítems y detalle. Se separan los bloques con « · » y se excluye texto de controles, usando texto DOM seguro. Ajuste visual compartido, sin cambiar formularios ni acciones; captura posterior al deploy verificada.

### Simulador comercial integral — 16/10/2026

- Promoción: piso $1.025, no cumple, propuesta cancelar promoción y actualizar precio; captura `image(20261016-164015).png`.
- Venta devuelta: conciliación devuelta, liquidación observada $0; la evaluación del precio usa liquidación esperada. Captura `image(20261016-164119).png`.
- Precio alto con envío: piso $33.800, liquidación esperada $29.200, observada $28.000, conciliación pago parcial y propuesta actualizar precio; `image(20261016-164213).png`.
- SIM-01: usuario confirma recálculo pero no percibe la acción. Se agrega estado de envío, confirmación tras POST exitoso, foco/desplazamiento al resultado o error y restauración al volver desde caché del navegador. Pendiente validación visual tras deploy.
- SIM-02: se alinea la casilla Promoción vigente y se explicita que la evaluación económica corresponde a liquidación esperada; aviso para ventas canceladas/devueltas sin alterar el motor. Pendiente validación visual tras deploy.
- Aviso global de vencimientos superpuesto al encabezado: pendiente de revisión; este ajuste local del simulador no lo modifica.

### Continuación: simulador, control y ficha comercial

- SIM-01 cerrado con `image(20261016-165108).png`: confirmación visible, foco sobre el resultado y valores conservados. La captura no acredita el estado transitorio del botón.
- Alineación Promoción vigente cerrada con `image(20261016-165205).png`; la aclaración sobre liquidación esperada se ve en el resultado.
- Control: Actualizar observado e Historial de precios disponibles. Emergente precarga $7.200, cuenta-uat y UAT-PUB-001. Historial legible, último registro del 03/10, registros manuales e importados conservados. No se guarda otro precio. Evidencias `image(20261016-165307).png`, `image(20261016-165356).png` y `image(20261016-165432).png`.
- Preparación bloqueada por precio/cargos/envío vencidos y advertencia de promoción vencida. Regla UAT-VALIDACION-001 v1 vigente: 168 horas para los cuatro datos. Configuración conservada; capturas `image(20261016-165529).png` y `image(20261016-165611).png`. Rentabilidad y vigencia son controles distintos.
- Ficha comercial: emergente con navegación y acciones fijas, producto sintético en borrador/no disponible, imagen visible y completitud 27%. Evidencias `image(20261016-165722).png`, `image(20261016-165733).png`, `image(20261016-165745).png` y `image(20261016-165756).png`. No se completan faltantes ni se activan canales.
- FUI-01: unificar tipografía y casillas de Imágenes/Canales/Relaciones, y ampliar espacio del selector de archivos recortado. CSS exclusivo de la ficha, sin modificar nombres, valores ni acciones. Pendiente validación visual después del deploy.

### Notificaciones bajo demanda — 16/10/2026

- FUI-01 cerrado con `image(20261016-192313).png`: selector de archivos completo, casillas alineadas y presentación consistente en Imágenes/Canales/Relaciones. No se guarda otra ficha.
- NUI-01: el usuario pide retirar el aviso permanente y acceder a notificaciones bajo demanda. Se reemplaza el contenedor flotante global por «Notificaciones» con campana y contador en la barra lateral, cerrado por defecto. Se reutiliza `alertas_operativas()` una sola vez, con los mismos avisos y enlaces, sin modificar consultas ni permisos. La cantidad indica avisos agrupados, no cantidad de obligaciones.
- Panel en flujo de la barra lateral, sin posicionamiento flotante ni apertura automática; estado vacío explícito. Se conserva el feedback temporal de las acciones.
- Pendiente UAT tras deploy: no aparece el cartel sobre el encabezado; Notificaciones abre/cierra y muestra el aviso de obligaciones con acceso a Revisar pagos. Las obligaciones no se marcan resueltas ni se altera su estado.

### Acceso a aceptación UAT y cierre de notificaciones

- NUI-01 cerrado: Notificaciones se ve plegado con contador y desplegado con aviso y enlace, capturas `image(20261016-194137).png` y `image(20261016-194149).png`. El usuario confirmó «perfecto» al verificar acceso a Pagos y vencimientos.
- NAV-01: el acceso a Aceptación por usuarios y roles estaba anidado en Preparación para reemplazar DUX. Se agrega enlace directo en la navegación superior de Estructura, junto a Control integral, a la ruta existente `admin_estructura.aceptacion_usuarios_operativos`. No se duplica pantalla ni se cambia validación/permisos. Pendiente validación tras deploy.
- Captura `image(20261016-194459).png`: aceptación abre por URL, sin resultado cargado; queda por uniformar su presentación antes de completar ese bloque de UAT.

### Presentación de aceptación UAT — 17/10/2026

- NAV-01 cerrado: usuario confirmó «perfecto» después del acceso directo publicado en `87250f04ddc0fc179dbd56e8d987102625f17e72`.
- AUI-01 confirmado por captura `image(20261017-135628).png`: controles nativos sin formato y acciones sin jerarquía. Se ordena la pantalla con encabezado, navegación, dos tarjetas de archivo, botones consistentes, estado/resumen, tablas contenidas, brechas y huella plegable. CSS limitado a esta pantalla. No cambia el contrato POST, validación, exportación ni permisos.
- `plantilla_resultados_uat.json`: organización 1, unidad 3, nueve casos por área y ocho pruebas DAT, todos pendientes y sin participantes. Es una plantilla inicial, no evidencia de casos fallidos ni aprobación; no se modifican sus resultados. El texto heredado de DAT-03 aún menciona confirmación escrita: conciliarlo antes de usar ese recorrido, sin repetir pruebas aprobadas.
- Pendiente tras deploy: revisar presentación inicial y luego resultados/error con archivos válidos de la campaña; no validar la plantilla vacía como si fuera un resultado completo.

### Presentación de preparación DUX — 17/10/2026

- AUI-01: visual inicial de aceptación cerrada con `image(20261017-140430).png`; archivos y acciones uniformes. Resultados y errores verificados solo con fixtures locales, aún sin evidencia visual de campaña en staging.
- PUI-01 confirmado con `image(20261017-140608).png`: selectores sin formato, casillas separadas de sus etiquetas y acciones nativas. Se reutiliza el estilo de aceptación UAT para las tres tarjetas de archivos, seis controles humanos, botones y resultado/brechas/huella.
- Se conservan archivos, nombres/valores de controles, POST y exportación, sin modificar el servicio ni marcar condiciones como confirmadas. Pendiente revisión visual inicial después del deploy.

### Expediente maestro — 17/10/2026

- PUI-01 cerrado con `image(20261017-143512).png`: tres archivos alineados, seis casillas junto a sus etiquetas y acciones uniformes. No se confirman controles humanos ni se genera una evaluación nueva.
- EMUI-01: `image(20261017-144705).png` muestra presentación antigua en expediente maestro. Se reutiliza CSS UAT para encabezado, selector múltiple, acciones, ayuda plegada, resumen, tabla contenida, hallazgos y huella. Se conservan formulario, controles y destinos existentes. Pendiente captura tras deploy.
- Revisión local de adjuntos con el servicio oficial: se identifican informes con huella válida para SaaS base, Compras, Tesorería y Contabilidad (organización 1; unidad 3 cuando se declara). Para Producción, Mantenimiento, Personas, Postventa y Transición DUX no se identificaron informes entre los JSON adjuntos actuales; esto no prueba falta de pruebas funcionales ni fallo. Conciliar antes de pedir nuevas pruebas.
- No cargar certificaciones individuales donde se requiere un expediente de dominio ni completar aprobaciones sin evidencia. La plantilla UAT sigue siendo un documento inicial por conciliar.

### Consolidación documental y visual de Producción — 17/10/2026

- EMUI-01: resultado visual confirmado en `image(20261017-152416).png`: 9 dominios identificados, 8 aprobados, 0 faltantes. Expediente maestro org. 1 / unidad 3, huella `5705e8b78577e968bdca2157d8f2787700f67b138f7e745d02c6f50a65cee099` verificada; estado incompleto por Transición DUX.
- Informes incorporados: Producción sin órdenes/partes/simulaciones; Mantenimiento sin planes/órdenes/tareas/repuestos; Personas sin cobertura ni vencimientos; Postventa sin casos/ítems/evidencias/propuestas. Sus controles técnicos sin hallazgos no acreditan circuitos funcionales. Reconciliar historial y contexto antes de repetir pruebas.
- Plan DUX exportado vacío a pedido: 13 pendientes, no apto para ensayo; no invalida UAT previa. Ensayo negativo con plantilla EJEMPLO-SKU/EJEMPLO-PEDIDO frente al snapshot sintético Fierro: 2 diferencias de productos y 1 pedido faltante, huella verificada. Prueba del detector, no conciliación real DUX. Expediente de transición bloqueado con plan_bloqueado y ensayo_con_diferencias; corte real no autorizado, efectos cero.
- PRUI-01: `image(20261017-153007).png` confirma secciones fuera del contenedor principal, distribución horizontal y controles sin estilo. Se incorpora contenedor único para toda la página, CSS exclusivo, tarjetas verticales, métricas compactas, alta plegada por defecto, formularios adaptables, acciones consistentes y tablas con desplazamiento interno. Informes agregados agrupados en panel plegado. Se mantienen campos, valores, condiciones, destinos y servicios existentes.
- Pendiente tras deploy: presentación de Producción vacía y con datos, apertura del alta, decisiones, avances y calidad. No se crea ninguna orden en este ajuste. Próximo UAT funcional: revisar contexto unidad 3 y registros antes de crear datos sintéticos.
- Pendiente visual confirmado: Plan de corte DUX, Ensayo offline y Expediente final de transición conservan controles nativos; aplicar formato común en un bloque posterior.

### Producción funcional y gestión de lotes — 17/10/2026

- PRUI-01: contenedor y alta verificados con capturas 154706, 161112 y 161631. Máquina sintética activada internamente para permitir planificación; no ejecución física.
- UAT-OP-001: revisión y aprobación interna verificadas; cantidad 10, costo congelado $49.336,50. Partes UAT-PARTE-001 (6 buenas, 1 rechazada, 90 minutos) y UAT-PARTE-002 (3 buenas, 45 minutos): acumulado 9 buenas, 1 rechazada, 0 pendientes, 135 minutos. Exceso de cantidad rechazado sin alterar acumulado.
- Simulación completa, propuesta de inventario bloqueada por mapeo de insumo faltante y destino ambiguo, y costeo sin hallazgos; huellas de los tres adjuntos verificadas. Costo unitario por buena $5.481,83. No cerrar la orden aún.
- Captura image(20261017-174659).png: UAT-LOTE-001 con 6 y UAT-LOTE-002 con 3, ambos en cuarentena y stock bloqueado. Los formularios abiertos, campos sin etiquetas y controles apretados motivan PRUI-02.
- PRUI-02: creación de lote plegada y visible solo con saldo de unidades buenas del parte, cantidad disponible precargada, tabla compacta y Gestionar en dialog nativo con etiquetas, ayuda, historial y Cancelar/X/Escape sin envío. Se conservan rutas, campos y validaciones del servicio. Pendiente deploy y UAT visual/cancelación/control.
- Pendientes conservados: etiquetas de avances preparatorios, presentación numérica general, gramática «El máquina», continuidad de scroll y visual de Plan de corte DUX, Ensayo offline y Expediente final de transición DUX.
