# Estado único de UAT — staging
Seguimiento iniciado: 16/10/2026, Argentina. Última incorporación: 19/10/2026.
Rama: `integracion-saas-2026-09`.
Base inicial: `379b6f6a86b80742064efbdc77706d979a526670`. Base de la ampliación ML del 18/10: `f90ffc0cf0f517aa85ad9b19fd82b186d4e96c6c`.

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

Siguiente bloque propuesto por prioridad del usuario (18/10): PML-0, contrato y ensayo offline de rentabilidad ML, definido al final de este documento. Las verificaciones anteriores se concilian con la evidencia de las secciones siguientes; no repetirlas por esta ampliación documental.

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

### Cruce Producción–Inventario — 17/10/2026

- PRUI-02: tabla de lotes desplegada verificada en image(20261017-175227).png y aprobación del lote 001 en image(20261017-175600).png. El usuario confirmó el rechazo del lote 002. No hay captura de la emergente ni confirmación aislada de Cancelar/X/Escape; conservar esa limitación de evidencia.
- evidencia_calidad_produccion.json: organización 1 / unidad 3, dos lotes y dos controles. Lote 001: 6/6 aprobadas; lote 002: muestra 3, aprobadas 2, rechazada 1. Huella f745011523191b8ee2b8be1a2a0b3c7debac02d72195c9c77f970f48a312bb92 válida, sin hallazgos, movimientos/liberaciones/conexiones cero. Aprobación del informe significa consistencia, no aprobación de todos los lotes.
- control_integral_produccion (1).json: 1 orden aprobada, 2 partes, 1 simulación completa, cero hallazgos/consumos/stock/costos/altas. Huella 0a6a62c21151ea0fe5a46bae0f22b15267a14d296121bd9914f7b781d81c043c válida y simulación coincidente con la anterior.
- expediente_habilitacion_produccion.json: huella dcf115a5fa6ac0de090acd02ffcd93d11b10694ade77fc49b6249d6c93565c23 válida. Costeo/capacidad/calidad consistentes; inventario y materiales bloquean aptitud. Habilitación de ejecución falsa, efectos cero. Plan de materiales: único hallazgo mapeo_faltante para insumo 1; huella dfb79baa98351a5580aab2c54b5f49348326a5d3c9ada99cd80adaad6fc16298 coincide con expediente. No infiere suficiencia de material.
- Capturas 180358/180411: producto UAT-PROD-001 conserva existencias 5 y 3 en dos depósitos activos. 180843: chapa sintética solo podía elegirse contra el producto terminado; no se guardó ese vínculo. 181329: preparación de SKU solo desde catálogo comercial; falta recorrido para materia prima.
- PINV-01: preparación individual de materia prima en Compras/Mapeo mediante insumo físico existente y SKU exclusivo. Reutiliza Producto como identidad física requerida por ItemInventario, sin inclusión en catálogo comercial; SKU tipo insumo, desactivado, unidad de medida en atributos. No crea existencias ni modifica cantidades. Repetición idempotente, colisiones rechazadas y preparación del catálogo no puede reclasificar una materia prima.
- PINV-02: nuevo mapeo exige existencia activa del SKU de ese insumo y contexto; rechaza producto terminado, otra unidad, otro insumo o control desactivado. Las propuestas conservan ejecución bloqueada. Los mapeos históricos no se modifican automáticamente.
- PINV-03: destino preparatorio elegible por orden entre existencias activas del producto principal. Persiste en ConfiguracionSistema con clave organización/unidad/orden; sin nuevas tablas ni columnas. Propuesta y expediente usan la misma selección y vuelven a validar contexto, producto, SKU y ubicación; destino seleccionado inválido bloquea sin elegir otro. Se conserva el comportamiento previo para órdenes sin selección.
- Validación local: 45 pruebas aprobadas, incluidas persistencia SQLite, idempotencia, colisiones, contextos ajenos, mapa incorrecto, destino inválido y transmisión de selección al expediente. Compilación Python y render Jinja vacío/con selección aprobados. No equivale a prueba contra PostgreSQL ni a revisión visual en Render.
- UAT pendiente después de deploy: preparar UAT-MP-001 desde insumo uat-ins-001, comprobar Cancelar, repetir sin duplicar, activar SKU y crear existencia en cero mediante Inventario existente, habilitar su control y crear mapeo correcto. Elegir destino de UAT-OP-001, verificar persistencia y actualizar solo informes afectados. No registrar ingresos ni consumos reales para aprobar informes. Inventario actual 5/3 conservado; revisar el uso práctico y el tratamiento de unidades fraccionarias antes de habilitar ejecución real (el inventario actual usa cantidades enteras).
- Permanecen pendientes visuales DUX y etiquetas/formatos de avances ya anotados. Producción/main fuera de alcance.

### Validación del cruce y faltantes — 17/10/2026

- PINV-01: emergente Preparar materia prima visualmente verificada en image(20261017-182633).png; SKU UAT-MP-001 creado desactivado sin existencias/stock en image(20261017-182809).png. Inventario muestra 2 SKU y 3 existencias: materia prima en cero y control desactivado; terminado conserva 5 y 3, captura image(20261017-183054).png. No se acredita prueba manual de repetición o Cancelar por estas capturas.
- PINV-02: image(20261017-190323).png confirma mapeo activo de uat-ins-001 a UAT-MP-001 en Depósito de prueba UAT. Propuesta de stock de UAT-REC-001 pasó de bloqueada a preparada; ejecución bloqueada, cuenta a pagar rechazada y costo aprobado conservados.
- PINV-03: propuesta_inventario_produccion_1 (1).json aprobada sin hallazgos, huella 6424d2471c57a53cf281caaae91f11bbdc11cf7445c8db0dd336fe8b54e8e1ff válida. Salida teórica 21 a existencia 3 e ingreso teórico 9 a existencia 2; simulación anterior coincidente. Controles confirman efectos cero. No hay captura aislada que pruebe el refresco del selector; sí que la exportación usa el destino elegido.
- expediente_habilitacion_produccion (1).json: apto para ensayo, habilitación de ejecución falsa, sin hallazgos; huella 934c5cd7fdf45df7ac9cae071f068dc37d39b3b0ab37f6b5465a2ad708889ff7 válida. Coinciden huellas de inventario y calidad. Materiales coincide con plan_materiales_produccion (1).json, huella 4d13ead5ca9ccb3855ede7e06a1aa1980f7af2f40b68b80e4f8883d40572d682. Este plan requiere cero porque UAT-OP-001 no tiene unidades pendientes; no prueba disponibilidad suficiente.
- Caso complementario UAT-OP-002-MATERIALES por una unidad en revisión: plan_materiales_produccion (2).json detecta requerida 2,1, asignada 0 y faltante 2,1 para insumo 1/existencia 3. Sugiere compra sin crear orden de compra, reserva o movimiento. Huella 1ce2bde3f9fca6a5c541aa16902d3731527959f08f3cbdbcd309313a8c556029 válida. El usuario respondió «perfecto» después de indicación de cancelar únicamente esta orden: cancelación confirmada por usuario, sin captura adicional. UAT-OP-001 continúa abierta.
- Alcance cerrado: recorrido preparatorio orden/partes/lotes/controles/costeo, mapeo correcto, destino explícito y detección de faltantes. No constituye habilitación de producción real, cierre ejecutado ni prueba manual completa de todos los rechazos/cancelaciones.
- Pendiente antes de cualquier ejecución: integrar elegibilidad de lotes por calidad y disponibilidad real al ingreso/consumo. La propuesta aún toma 9 buenas del parte y no excluye el lote rechazado. El indicador aprobado de materiales expresa consistencia aunque haya faltantes; distinguirlo de disponibilidad suficiente en la presentación y en cualquier futura decisión de habilitación. Cantidades fraccionarias del inventario siguen pendientes.
- Siguiente revisión independiente: Mantenimiento preparatorio, ruta /admin/mantenimiento. El expediente previo vacío no acredita UAT funcional. Revisar pantalla/contexto y evitar repetir registros existentes.

### Mantenimiento: presentación previa al UAT funcional — 17/10/2026

- MANT-UI-01 confirmado por image(20261017-191628).png y image(20261017-191640).png: unidad Ensayo UAT, máquina uat-maq-001 disponible, cero planes/órdenes/tareas/repuestos; métricas concatenadas, formularios abiertos, campos sin etiquetas y botones nativos.
- Se reutiliza el CSS y comportamiento de plegado existentes de los paneles preparatorios: contenedor vertical, tarjetas, métricas compactas, formularios plegados, etiquetas permanentes, acciones uniformes, Cancelar sin enviar en formularios de alta y tablas contenidas. Cancelación de orden queda plegada bajo su acción, conservando motivo y validación. Se conservan campos, valores, opciones, destinos y condiciones originales; no cambia servicio, base ni estados.
- Pendiente tras deploy: visual inicial y apertura de Nuevo plan preventivo, cancelación sin crear registro y primer plan sintético sobre la máquina existente. No se creó un plan durante el ajuste. Informes vacíos previos no acreditan el flujo funcional.
- Verificación local: render vacío, con órdenes planificada/cancelada y con mensaje de error; contratos de formularios/opciones/enlaces idénticos al original, etiquetas presentes, paneles cerrados y botones Cancelar sin envío. Sin prueba visual automatizada contra Render.

### Mantenimiento: circuito preparatorio verificado — 17/10/2026

- MANT-UI-01 desplegado: capturas 193045/193101 confirman presentación inicial y apertura del formulario. Captura 193319 confirma UAT-MANT-PLAN-001 creado inactivo sobre uat-maq-001; próxima fecha 20/10/2026, frecuencia 30 días. Captura 193505 confirma una tarea pendiente sin completar. No se acredita prueba aislada de Cancelar en el alta.
- Usuario confirmó orden preventiva planificada por $1.000 y repuesto UAT-REP-001, cantidad 1, costo estimado $250.
- control_mantenimiento_preparatorio.json: organización 1/unidad 3, plan 1 próximo en tres días, costo de órdenes 100000 centavos, aprobado sin hallazgos, controles de ejecuciones/stock/compras/conexiones en cero. Huella 009aa8451a4b0cd8224351a5eb0cd44958dc22719458f7c0a960e6b53f95a195 verificada.
- expediente_mantenimiento (1).json: un plan, una orden, una tarea y un repuesto; carga 2026-S43 con una orden por 100000 centavos y repuestos 25000 centavos, sin impactos ni hallazgos. Huella c362423337c12512c156fef450fa80d1fbbcfe067c7ac4d544ebd7864125644e verificada.
- Usuario confirmó cancelación con motivo Cierre de ensayo UAT sin ejecución. expediente_mantenimiento (2).json conserva un plan, orden, tarea y repuesto; carga_semanal vacía, repuesto histórico 25000 centavos, aprobado sin hallazgos y controles en cero. Huella 0ef0196610572292ba6761b8beea085624189f4286fb23191df00784b58be450 verificada. El JSON agregado no expone estado/motivo por registro; la cancelación se acredita por confirmación del usuario y desaparición de la carga planificada.
- Alcance validado: alta de plan/tarea/orden/repuesto y cancelación conservando historial, sin ejecución real. No equivale a UAT completo de todos los rechazos ni a habilitación operativa.

### Personas: presentación previa al UAT funcional — 17/10/2026

- PERS-UI-01: captura image(20261017-194752).png confirma un empleado ficticio uat-emp-001, cero turnos/novedades/conflictos, formularios abiertos, métricas concatenadas, campos sin etiquetas permanentes y botones nativos.
- Se reutilizan produccion.css y produccion.js ya validados en Mantenimiento: contenedor único, tarjetas, métricas compactas, alta de turno/novedad/competencia plegada, etiquetas permanentes y acciones compactas. Cancelar restablece y cierra el formulario sin envío; cancelación de turno queda plegada con motivo y opción Volver. No se incorporan servicios ni comportamiento duplicado.
- Campos, restricciones, opciones, enlaces, acciones y condiciones de visibilidad conservados. Sin cambios de rutas, servicios, esquema, datos, nómina o fichajes. Solo presentación y documentación; producción/main fuera de alcance.
- Verificación local: render sin empleados, con empleado/turnos planificado y cancelado/novedad/competencia, y con error escapado. Contratos originales de formularios/campos/opciones/enlaces idénticos; etiquetas presentes, formularios sin anidar, detalles cerrados y botones de retorno type=button. Sin prueba visual automatizada contra Render.
- Pendiente tras deploy: visual inicial y apertura/cancelación de Nuevo turno; continuar UAT funcional con empleado existente, sin duplicarlo. Se conservan pendientes de Producción/calidad/stock/fracciones y visual DUX.

### Personas: acción de cancelación compacta — 17/10/2026

- Captura image(20261017-195741).png confirma turno 1 planificado sin fichaje para uat-emp-001, 20/10/2026 08:00–12:00, sector Producción UAT; una fila y cero novedades/conflictos. No acredita por sí sola la cancelación del formulario de alta.
- PERS-UI-02: desplegable Cancelar turno agranda la fila y desentona con las acciones. Se reemplaza por botón compacto Cancelar y dialog nativo con motivo, Confirmar cancelación, Volver y cierre X/Escape. Reutiliza CSS/JS de ventanas existentes; restablece el formulario al cerrar, sin envío al volver/cerrar. No cambia ruta, campos, motivo mínimo de cinco caracteres ni servicio de cancelación.
- Render local vacío y con dos turnos planificados y uno cancelado: identificadores únicos, destinos de ventanas correctos, ventanas cerradas inicialmente, sin formularios anidados, retorno type=button, cancelado sin acción y texto escapado. Pendiente revisión visual y cancelación en Render; mantener el turno para completar evidencia antes de cancelarlo.

### Personas: evidencia funcional posterior — 17/10/2026

- Usuario confirmó retorno desde Cancelar turno mediante Volver conservando el turno, y alta de novedad de 30 minutos extra propuestos. No hay captura aislada de X/Escape.
- control_personas_preparatorio.json: organización 1/unidad 3, turno el 20/10/2026 de 240 minutos; aprobado, sin hallazgos, controles en cero. Huella fd38a20a1b53c2854ffcddad8f0b0612f1c5e93d63b0f3a9bae13a46e600b1c2 verificada.
- expediente_personas_preparatorio (1).json: un empleado en Producción UAT con 240 minutos de cobertura, 30 minutos extra propuestos y competencia 1 próxima a vencer el 20/10/2026. Sin asignaciones habilitadas, fichajes, novedades aprobadas, liquidaciones, cambios de costos ni conexiones. Huella 7ee342c421fd08ffad46dc82718321ef2574bd38389b1e84931d6c130216ec93 válida.
- Tras indicación de cancelar el turno con motivo Cierre de ensayo UAT sin fichaje, expediente_personas_preparatorio (2).json muestra cobertura vacía, mantiene 30 minutos propuestos y competencia; sin hallazgos y controles cero. Huella ea392ff0623c4616261c32ed86eb0ecadcfa4596b3d5aa77dff0fd9addc45eb8 válida. El agregado no prueba por sí solo el texto del motivo ni el detalle histórico del turno.
- Alcance validado: recorrido preparatorio turno/novedad/competencia y retiro de cobertura al cancelar. No equivale a validar todos los rechazos ni a habilitar operaciones laborales. Novedad sigue propuesta y competencia no habilitante.

## Ampliación del plan: Rentabilidad y publicaciones de Mercado Libre — 18/10/2026

Estado: propuesta registrada el 18/10/2026. Primer ensayo PML-0A implementado con alcance y pendientes detallados al final; conectores y operación real todavía no implementados.
Prioridad indicada por el usuario: rentabilidad real antes de revisión de publicaciones, competencia e IA.
Base auditada: f90ffc0cf0f517aa85ad9b19fd82b186d4e96c6c, rama integracion-saas-2026-09. GitHub es fuente oficial.
Este bloque amplía el plan vigente; no reemplaza pendientes de calidad/materiales de Producción, fracciones de Inventario, visual DUX, Postventa y aceptación final. Mantener un único seguimiento aquí.
Solo se cambia documentación en esta incorporación. Sin cambios de producción/main, esquema, estados operativos, OAuth, permisos, scheduler, webhooks ni conexiones. Laboratorio desconectado y bootstrap deshabilitado.

### Qué existe y debe reutilizarse

| Capacidad | Evidencia en código | Decisión |
| --- | --- | --- |
| Producto/SKU, ficha técnica, variantes, imágenes y texto por canal | models/catalogo_producto.py; services/catalogo_ficha_integral.py | Mantener el maestro existente. La completitud y validación local de imágenes ya existen; agregar diferencias frente a la publicación, sin segundo catálogo. |
| Costos de compra/producción/combos e historial | models/perfil_costeo_producto.py; models/costo_producto_version.py; models/costo_producto_detalle.py; services/costos_productos.py; services/composicion_costo_producto.py | Reutilizar versiones y detalles. No sustituir una venta histórica por el costo vigente de hoy ni confundir costo calculado con costo realizado. |
| Reglas de canal, piso, comisión, cargo fijo, envío, publicidad, financiación y devolución estimados | services/motor_comercial_canal.py; services/reglas_economicas.py | Reutilizar cálculo previsto. Las reglas configuradas no son cargos reales de ML. No volver a restar la utilidad objetivo como gasto. |
| Simulación prevista y comparación con liquidación informada | services/simulador_integral_comercial.py | Mantener simulador como escenario; no convertir sus entradas manuales en liquidaciones verificadas. |
| Venta observada, costo congelado y movimientos financieros | models/conciliacion_ventas_canal.py: VentaCanalItem, MovimientoLiquidacionCanal, GestionConciliacionCanal; services/conciliacion_liquidaciones_canal.py | Ampliar este circuito como núcleo del resultado observado. Ya hay costo snapshot, expectativa y neto observado; falta desglose económico completo y trazabilidad por línea ML. |
| Importación de ventas/movimientos y extracto MP, lotes, gestión y cierres | services/importacion_conciliacion_canal.py; services/importacion_extracto_mp.py; /admin/comercial/conciliacion y sus rutas | Mantener importación y conciliación existentes. El extracto MP actual ingresa netos; no garantiza por sí mismo el detalle de todos los gastos. |
| Identidad de publicación/variante/cuenta y precios/cargos/envíos observados | models/mapeo_publicacion_canal.py; models/observacion_comercial_canal.py; services/inventario_mapeos_publicacion.py; services/importacion_datos_comerciales_canal.py | Reutilizar cuenta exacta, mapeos e historial. Precio actual/observación comercial no reemplaza precio efectivo de una venta histórica. |
| ML multicuenta y packs completos | services/ml_api_context.py; modules/bot_ml/orders_api.py; services/ml_pack_items.py; models/pedido.py | Usar contexto explícito de cuenta y validar seller, organización y unidad. No cambiar la importación operativa para obtener rentabilidad. |
| Ensayos sin red y barreras | services/certificacion_offline_mercado_libre.py; services/certificacion_offline_mercado_pago.py; services/seguridad_entorno.py | Extender ensayos con archivos sintéticos, sin crear una conexión paralela. billing.py y /orders/{id}/billing_info actuales tratan datos del comprador, no conciliación de cargos facturados. |

### Brechas y riesgos confirmados del cálculo actual

1. PML-01 — Mapeo de varias publicaciones al mismo SKU. MapeoPublicacionCanal impone unicidad por organización/vínculo/inclusión y por identidad externa. La primera restricción impide varias publicaciones del mismo producto en un vínculo. Diseñar ampliación compatible y migración explícita, revisar consumidores de Inventario y cola antes de cambiarla. No resolver duplicando productos ni inclusiones artificiales. Mantener identidad externa y variante únicas dentro de cuenta; la unidad se valida a través del vínculo.
2. PML-02 — Detalle financiero sin agrupar prematuramente. PedidoItem conserva SKU/cantidad/devolución, sin precio ni cargo por línea. ml_agrupar_items suma por SKU y conserva precio/cargo de la primera fila: correcto como proyección operativa de cantidades, insuficiente como libro financiero. En memoria, dos líneas del mismo SKU con precios 100/200 y cargos 10/30 se convierten en una fila con cantidad 2, precio 100 y cargo 10. Conservar órdenes/líneas originales y obtener totales financieros antes de cualquier agregado; incluir cancelaciones/devoluciones excluidas del importador operativo.
3. PML-03 — Ámbito de cargos y asignación. calcular_expectativa aplica el motor por unidad y multiplica también el envío. En memoria, envío unitario configurado 10000 centavos y cantidad 2 genera envío esperado 20000. No prueba error del caso UAT previo; sí falta tratamiento de un único shipment/pack compartido. Separar unidad, línea, orden, pack/envío y período. El total del envío se cuenta una sola vez; cualquier reparto por SKU se identifica como asignación, con regla versionada y suma exacta al total.
4. PML-04 — Neto y detalle sin doble descuento. conciliar_venta suma los movimientos marcados impacta_saldo. En memoria, neto 90000 más débito de comisión 10000 produce 80000. Si esa comisión ya integraba el neto, debe ser informativa, no otro impacto. Definir relación de documentos/movimientos y precedencia antes de mezclar extracto, orden y facturación; no sumar sale_fee y cargo facturado como gastos independientes del mismo concepto.
5. PML-05 — Margen económico distinto de conciliación. El control actual compara liquidación esperada con piso económico. No calcula un margen observado completo por publicación ni resta en ese informe el costo snapshot, embalaje y gastos externos identificados. Costo snapshot existe, pero no incluye identificador de versión; ampliar procedencia.
6. PML-06 — Datos faltantes y vigencia. Algunos normalizadores offline usan cero para campos opcionales ausentes y el simulador distingue pagos pendientes a partir de real=0. En rentabilidad, ausente no puede equivaler a cero confirmado; neto cero puede ser un resultado real. Necesitamos presencia, procedencia, fecha, cobertura y estado financiero explícitos.

Son comprobaciones locales en memoria contra el código de la base auditada; no se consultó ML ni se escribió en una base.
No se ejecutó la suite pytest en esta auditoría: el runtime local no tenía pytest. No se declaran pruebas completas aprobadas.
La búsqueda global de GitHub devolvió incomplete_results=true; no se usa para demostrar ausencia total de endpoints. Las conclusiones se limitan a archivos y rutas inspeccionados.

### Viabilidad de la API oficial: documentado frente a comprobado en cuenta

Consulta documental: 18/10/2026, mediante páginas oficiales indexadas. Algunas aperturas directas devolvieron HTTP 403 del sitio de documentación; no son respuestas de la API de la cuenta.
No se usaron credenciales, no se inspeccionaron tokens ni grants, no se probaron endpoints de vendedor. Disponibilidad documental no equivale a acceso autorizado/efectivo del usuario.

| Necesidad | Recurso documentado | Alcance y límite de la propuesta |
| --- | --- | --- |
| Publicación, variante, SKU, cantidades y precio efectivo por venta | GET /orders/{id}; GET /packs/{id}; GET /items/{id} | Orden/línea como base financiera; pack conserva pertenencia. SKU externo es indicio validable, no coincidencia automática por título. Leer SELLER_SKU/variación y contrastar mapeo. |
| Comisión observada y descuentos | order_items.sale_fee; GET /orders/{id}/discounts | Separar cargo por unidad y cantidad. Distinguir descuento del vendedor y aporte ML; no descontar de nuevo lo ya incluido en precio efectivo. Descuentos no cubren cargos adicionales o devoluciones posteriores. |
| Envío a cargo de cada parte | GET /shipments/{id}/costs | Usar sender correspondiente a la cuenta; separar receiver. Un shipment compartido no se multiplica por línea. En Acordás/transporte externo, costo y cobro deben venir del registro/comprobante propio; si faltan, resultado parcial. |
| Cargos y bonificaciones facturados, pagos y ajustes | GET /billing/integration/group/ML/order/details?order_ids=... o pack_id=...; detalles por período/documento | Conciliar cargos y referencias, detectar datos tardíos y revisión de períodos. Hasta 60 órdenes por consulta en el recurso documentado; paginar. No suponer para Argentina bloques que la documentación marca exclusivos de Brasil. |
| Precio previsto/cotización de cargos | GET /sites/MLA/listing_prices; /items/{id}/sale_price para precio observado actual | Cotización fechada, no gasto realizado. Listing prices requiere contexto de categoría, tipo, logística, shipping_mode y peso facturable en Argentina; no fijar umbrales ni porcentajes universales. |
| Ficha pública y requisitos | /items/{id}, /items/{id}/description, /categories/{id}/attributes | Comparar contra ficha existente y requisitos de categoría. Metadatos/cantidad/medidas de imágenes no prueban calidad visual ni conversión; revisión humana. |
| Competencia | /items/{id}/price_to_win para catálogo; datos de ítems/búsquedas permitidos | Catálogo no equivale a todo el mercado. Acceso/condiciones/equivalencia por verificar; solo observaciones fechadas, sin prometer ventas reales o márgenes de competidores ni scraping como sustituto automático. |
| Publicidad | Recursos Advertising según permiso y versión vigente | Documentación de Product Ads publica inversión y atribución; varias rutas de métricas antiguas figuran deprecadas. Confirmar Ad Groups vigente al implementarlo. No se acredita costo publicitario exacto por venta: reparto por publicación/período es asignación explícita. |
| Permisos y acceso | Permisos funcionales: ventas/envíos, publicación, facturación y publicidad según recurso | Tratar 401/403/429, datos no disponibles y fuentes pendientes; no activar permisos ni conexiones como parte del UAT desconectado. No prometer histórico ilimitado. |

Referencias oficiales utilizadas:
- Órdenes y descuentos: https://developers.mercadolibre.com.ar/es_ar/metricas/gestiona-ventas y https://developers.mercadolibre.com.ar/es_ar/trabajar-con-imagenes/gestiona-ventas
- Packs: https://developers.mercadolibre.com.ar/gestion-packs
- Provisiones/cargos por orden y pack: https://developers.mercadolibre.com.ar/es_ar/pagos/provisiones
- Costos previstos: https://developers.mercadolibre.com.ar/comision-por-vender
- Envíos: https://developers.mercadolibre.com.ar/es_ar/envios
- Atributos y descripción: https://developers.mercadolibre.com.ar/atributos y https://developers.mercadolibre.com.ar/descripcion-de-articulos
- Competencia: https://developers.mercadolibre.com.ar/competencia-en-catalogo
- Advertising: https://developers.mercadolibre.com.ar/product-ads-para-catalogo-y-user-products-lectura
- Permisos: https://developers.mercadolibre.com.ar/permisos-funcionales
- Productos/User Products: https://developers.mercadolibre.com.ar/en_us/api-docs/list-products
- Búsquedas y migración bulk: https://developers.mercadolibre.com.ar/es_ar/guia-para-carrito-de-compras/items-y-busquedas

Documentación reciente señala migración a /items/bulk para consultas múltiples antes del 25/10/2026. Revalidar al construir el lector; no extender consultas antiguas /items?ids=. Esto no afirma que el código actual las use.
Para IA, verificar modelo de publicación tradicional/catálogo/User Products: la documentación ya distingue comportamiento del título. No prometer edición universal de título ni aplicar una sugerencia automáticamente.

### Definición del resultado y de su evidencia

Propuesta de cálculo económico: ingreso de la venta atribuible al vendedor, después de descuentos financiados por él y con aportes/bonificaciones acreditados, menos cargos efectivos, logística a su cargo, costo del producto y embalaje no incluidos antes. Cada evento tiene una única incorporación contable al resultado; no reconstruirlo restando descuentos dos veces al precio final.
Mostrar separadamente flujo de cobros/liberaciones y resultado económico. Retenciones/percepciones y tratamiento de impuestos recuperables requieren clasificación explícita; no llamar a todo débito gasto ni deducir tasas fiscales genéricas del margen. Mantener base monetaria/impositiva comparable.
No usar solamente neto depositado menos costo para afirmar ganancia final: puede faltar un cargo, haber saldo retenido, reembolso, publicidad, transporte externo o componente ya incluido.
Margen sobre venta = resultado / ingreso económico de venta; denominador cero => no calculable. Mostrar importe, porcentaje y diferencia respecto del previsto; no confundir con recargo sobre costo ni con excedente del piso objetivo.

Por componente guardar: concepto, moneda y centavos, cantidad/alcance, fuente y referencia externa, fecha del hecho/consulta, evidencia o huella, estado (observado, estimado, asignado, faltante o cero confirmado), versión/costo/política y relación con otros cargos. No guardar tokens ni datos personales innecesarios.
Costo de producto: enlazar versión/detalles aplicables a la fecha de la venta; si se usa costo histórico aprobado pero calculado, decirlo. Sin versión histórica suficiente, mostrar pendiente o reconstrucción identificada, nunca sustituir silenciosamente por la actual.
Embalaje: comprobar primero si integra detalles del costo existente; cargar solo diferencia separada cuando corresponda. Materiales de embalaje y gastos propios son información interna, no promesa de la API.
La publicidad estimada y provisiones de devoluciones del motor previsto no se suman a un gasto real equivalente sin reemplazo o conciliación.
Estados separados:
- Previsto: usa reglas/cotizaciones y costo identificado.
- Observado parcial: hay movimientos efectivos pero faltan conceptos o solo hay imputaciones.
- Conciliado al corte y con alcance declarado: referencias, importes y gastos aplicables reconciliados; se detallan los costos históricos/calculados y asignaciones.
- No calculable: falta identidad/costo esencial o hay incompatibilidad de moneda.
No presentar Rentabilidad real completa en verde cuando falte una fuente obligatoria. Un control estructural aprobado o una venta pagada no certifican ganancia final.

### Incorporación por etapas

| Etapa | Entrega | Condición de cierre |
| --- | --- | --- |
| 0 — Contrato económico y datos, siguiente bloque | Identidad y cardinalidad, fuentes, ámbitos de gasto, precedencia de netos/desgloses, snapshots y conjuntos de ensayo. Servicio puro de análisis offline que use el motor previsto y conciliación existentes. | Casos PML-UAT de abajo aprobados y reporte exportable; cero red/efectos externos. |
| 1 — Rentabilidad por publicación y venta, prioridad inicial | Vista de previsto/observado/diferencia y detalle de incluidos/faltantes; agregados por SKU, publicación, cuenta y período; comparación congelada. Ampliar VentaCanalItem/MovimientoLiquidacionCanal mediante migración revisada solo donde falte trazabilidad. | Coinciden importes y referencias, sin duplicación; presentación y cierre sin guardar validados. Primero archivos sintéticos; datos reales solo en futuro bloque autorizado y por cuenta exacta. |
| 2 — Revisión de publicaciones | Diferencias entre ficha de catálogo y snapshot de publicación, atributos requeridos, títulos e imágenes; oportunidades explicadas. | Sin duplicar el editor ni confundir completitud local con ranking/calidad ML; propuestas revisables. |
| 3 — Competencia | Comparación de equivalentes, precio/condiciones/logística/fecha y fuente; soporte de catálogo donde aplique. | Indicar observado/estimado/no disponible y universo comparado. No prometer datos financieros privados de terceros. |
| 4 — IA con revisión | Propuestas de títulos/descripciones a partir de ficha validada; diferencias y respaldo de cada característica. | No inventar materiales, dimensiones, certificaciones, stock o promesas. Borrador/revisión; proveedor IA y publicación siguen desconectados durante UAT. |

Diseño propuesto: Comercial → Mercado Libre → Rentabilidad y publicaciones, sujeto a consolidación del menú comercial existente. No es una ruta implementada.
Pestaña inicial Rentabilidad; Publicaciones, Competencia y Propuestas IA se incorporan cuando estén listas, sin pantallas vacías simulando funciones.
Reutilizar estilos/componentes de Comercial y Conciliación: barra lateral, filtros compactos por unidad/cuenta/período, tablas paginadas contenidas, importe y margen previsto/observado/diferencia, estado de integridad y botón Gestionar/Ver detalle en modal.
En detalle: desglose de conceptos, incluidos/faltantes, documento de origen y fecha de corte; sin formularios permanentemente abiertos. Cancelar/X/Escape sin envío, confirmación simple, retorno al registro y feedback visible. No segundo editor de productos, segundo historial de costos o segunda caja de conciliación.
Arquitectura: consulta acotada por contexto; servicio de resultado separado del acceso ML; adaptador de lectura futuro detrás del contexto existente; snapshots/evidencia sin modificar Pedido ni la proyección logística. La sesión de usuario no reemplaza verificar propiedad de cada dato importado.
Vínculos orden–pack–línea–pago–movimiento conservan todos sus identificadores. Múltiples pagos y actualizaciones no deben entrar en el único campo referencia_pago como si fueran un solo evento; diseñar relación complementaria compatible con los registros existentes.
Cambios de esquema/cardinalidad se implementarán y probarán por separado, con migración explícita. No usar bootstrap para agregar columnas a ciegas.

### Próximo UAT seguro: PML-0, todavía por implementar

Solo organización 1/unidad 3 y cuenta de ensayo existente validada por el sistema. Fixtures con IDs inequívocamente ficticios, sin abrir conexión ML/MP/IA. No pedir al usuario que copie tokens ni ejecute scripts sobre producción. Datos de negocio previamente aceptados se reutilizan por referencia, sin duplicar altas.
No declarar ninguna de estas pruebas ejecutada por estar escrita aquí:

| Caso | Verificación y resultado esperado |
| --- | --- |
| PML-UAT-01 | Venta simple con costo/embalaje/cargos documentados: reconstrucción exacta, margen y diferencia explicados, ninguna deducción repetida. |
| PML-UAT-02 | Cuatro órdenes en un pack, SKU repetido con distinto precio/cargo: todas las líneas originales suman correctamente; envío compartido contado una vez. |
| PML-UAT-03 | Dos unidades y un envío; reparto por SKU visible como asignado, redondeo conservando el total del comprobante. |
| PML-UAT-04 | Neto con cargos ya incluidos y el mismo detalle de facturación: conserva neto sin otro débito. Cobertura incompleta/movimientos sin clasificar => pendiente. |
| PML-UAT-05 | Promoción cofinanciada y descuento en precio: distingue aportes ML/vendedor, no suma ni resta el mismo descuento dos veces. |
| PML-UAT-06 | Cambiar costo vigente después de la venta: resultado histórico no cambia; costo sin versión a esa fecha => faltante, sin cero automático. Embalaje ya dentro del costo no se duplica. |
| PML-UAT-07 | Anulación/reembolso/devolución parcial y nota de crédito posterior: reconciliar eventos sin borrar historial; no confundir devolución de dinero con reposición automática de producto. |
| PML-UAT-08 | Publicidad asignada, transporte externo faltante y retención sin clasificación: declarar alcance parcial, no certificar ganancia neta final. Neto cero confirmado distinto de ausencia de pagos. |
| PML-UAT-09 | Mismo SKU o ID en otra cuenta/organización/unidad, variante no mapeada o pack incompleto: bloquear cruces y evitar fallback a primera cuenta; varios anuncios del mismo SKU sin duplicar el maestro. |
| PML-UAT-10 | Archivo/movimiento repetido, páginas repetidas o evento corregido: idempotencia y trazabilidad; 401/403/429/respuesta incompleta simulados dejan fuente pendiente, no importes cero. |
| PML-UAT-11 | Moneda incompatible, NaN/infinito/importe no representable, cantidad inválida, evidencia alterada: rechazo legible sin registros parciales. |
| PML-UAT-12 | Pantalla vacía/con datos/móvil, abrir detalle y cerrar Cancelar/X/Escape: sin escrituras accidentales; feedback visible y posición conservada. |

Antes de construir, cerrar el contrato de precedencia/ámbitos y compatibilidad de mapeos. Después implementar únicamente PML-0/1 offline con pruebas unitarias e integración centradas en estas brechas, y recién entonces pedir pruebas de pantalla. No corresponde deploy por este documento.

## Ampliación autorizada: mayoristas ML y centralización operativa ML/MP — 18/10/2026

El usuario autorizó registrar la propuesta anterior en este documento y pidió revisar mayoristas y centralizar publicación, venta, costos, envíos, cobros, liquidaciones y control de MP. Esta autorización se aplica al registro documental; este commit no implementa conectores ni habilita operaciones externas.
Mantener rentabilidad como primera entrega. Mayoristas B2B y control de cuenta MP pasan a ser requisitos del contrato de datos inicial, no motores separados.

### Mayoristas: hechos documentados y límites de Argentina

Fuentes oficiales consultadas el 18/10/2026; no se consultó una cuenta de vendedor.
- Mercado Libre documenta PxQ B2B para MLA con habilitación controlada del vendedor (tag business); no acredita que Fierro ya sea elegible. La modalidad mayorista interna de Fierro no acredita elegibilidad ML.
- Documenta transición de importes absolutos a porcentajes el 27/10/2026. El recurso anterior se conserva para precios netos, funcionalidad que su guía limita a Brasil; no ofrecerla como disponible en Argentina.
- PxQ B2C tiene alcance documentado restringido a neumáticos: no asumir su aplicación al catálogo de Fierro.
- La página comercial anuncia beneficios de envío y cargo fijo con condiciones y excepciones. No convertirlos en descuento universal ni en cargo cero fijo en el motor; contrastar cotización, logística y cargo observado.
- En el modelo porcentual se documentan hasta cinco tramos, lectura con show-all-prices: true en /items/{id}/prices, consulta /sale_price con contexto business y quantity, marca b2b en órdenes, recomendaciones previas y escritura en /items/{id}/prices/price-per-quantity. Las recomendaciones no incorporan el costo interno completo del producto.
- La guía presenta una discrepancia entre los límites de cantidad de Consideraciones y el body de configuración; revalidar antes de implementar el validador de escritura. No derivar un contrato definitivo de ejemplos de otro site.

Referencias:
- Elegibilidad y cambio de modelo: https://developers.mercadolibre.com.ar/es_ar/precio-por-cantidad
- Porcentajes, recursos, marcas y recomendaciones: https://developers.mercadolibre.com.ar/es_ar/categorias-y-atributos-inmuebles/pxq-porcentaje-b2b
- B2C limitado por dominio: https://developers.mercadolibre.com.ar/es_ar/feedback-sobre-venta/precios-por-cantidad-b2c
- Precios netos exclusivos de Brasil: https://developers.mercadolibre.com.ar/es_ar/pagos/precios-netos
- Beneficios comerciales condicionados: https://vendedores.mercadolibre.com.ar/aprender/nota/precios-mayoristas-vendes-mas-pagas-menos?guideKeyId=GE79

### Auditoría adicional de lo existente

| Elemento revisado | Existe | Falta para este objetivo |
| --- | --- | --- |
| ListaPrecio | Tipo mayorista y listas por organización/unidad. | No equivale a tabla PxQ de ML. Reutilizar listas y políticas; agregar contrato versionado de tramos/contexto sobre publicación, sin segundo SKU/producto por umbral. |
| ListaPrecioItem | Precio histórico enlazado con versión de costo y política. | Un precio vigente por lista/inclusión; sin tramo mínimo de cantidad en este modelo. Diseñar relación compatible para tramos, no sobrescribir precio minorista. |
| ReglaCanalVersion/ReglaCanalCargoTramo | Comisiones y costos previstos; tramos por precio. | Tramo de cargo según precio no es tramo de descuento según cantidad. Mantener separados los conceptos usando el mismo motor económico. |
| Pedido/PedidoItem y sincronización de ítems | Identidad operativa ML y proyección SKU/cantidad para logística. | En los modelos y sincronizadores inspeccionados no hay snapshot explícito de tabla PxQ, tramo ganador o flujo B2B. No concluir ausencia en todo el repositorio a partir de búsquedas parciales. |
| VentaCanalItem/MovimientoLiquidacionCanal | Venta económica y movimientos por referencia_venta obligatoria. | Lectura financiera de todas las líneas, múltiples pagos, tramos B2B y movimientos de cuenta sin venta. No inventar referencia de venta para retiros/transferencias. |
| CierresConciliacionMP/legajo/certificación integral | Snapshots, decisiones, cierres y exportación de evidencia sin red. | Extender los mismos cierres a cobertura por período/tipo de reporte, integridad de cuenta y hechos tardíos. Un cierre técnico no certifica la totalidad del saldo MP. |
| CuentaTesoreria y MovimientoTesoreriaProyectado | Cuentas internas, billetera_virtual, saldo inicial y proyecciones con restricciones offline. | No son libro real de MP: las proyecciones impiden afectar saldo y las cuentas impiden conexión externa. No levantar esas restricciones para importar reportes ni llamar saldo real a una proyección. |
| Conciliación offline de Tesorería | Lectura de extractos y candidatos por tipo/importe/fecha, sin efectos. | Candidato no es coincidencia financiera confirmada. Relacionar con identidad de pago/operación/documento antes de vincular entre módulos. |

Archivos adicionales leídos: models/lista_precio.py, lista_precio_item.py, politica_comercial_lista.py, regla_canal.py, vinculo_canal_comercial.py, tesoreria.py; services/ml_items.py, ml_importacion_cuentas.py, cierres_conciliacion_mp.py, certificacion_integral_mp.py, legajo_rendicion_mp.py, conciliacion_offline_tesoreria.py y control_liquidez_tesoreria.py.
No se alteran los campos ml_* ni domain.estados/app.py: el dato financiero se vincula al pedido, sin dirigir su estado operativo.

### Contrato propuesto para B2B dentro de Rentabilidad

Guardar por cuenta/publicación/variante y versión: tipo de tabla (legado absoluto, porcentaje, neto fuera de alcance MLA), fuente, sitio/moneda, fecha, elegibilidad desconocida/confirmada/no disponible, tramos y contexto de comprador. El dato no disponible se conserva como tal; no activar business desde Fierro ni crear una cuenta alternativa.
Guardar snapshot de la orden sin inferir mayorista por tener CUIT o por comprar varias unidades. Marcas/contexto de ML, cantidad adquirida, unidad comercial, price_id y evidencia de tabla aplicable permiten explicar la clasificación. Precio cobrado de la orden tiene prioridad para el hecho histórico; no recalcular una venta pasada con la tabla actual.
No confundir pack de carrito con producto comercial vendido como pack. Un SKU que representa diez unidades físicas cuenta como una unidad comercial al aplicar la tabla de esa publicación, salvo contrato explícito distinto. Registrar factor físico para costeo/embalaje, sin multiplicar cantidad financiera dos veces.
Para cada tramo propuesto, calcular importe y margen por unidad y por operación, envío compartido, embalaje incremental, descuento vigente y costo histórico. Marcar ahorro logístico como cotizado o observado según evidencia; una estimación ML de ganancia no equivale al resultado Fierro después de producto/embalaje/cargos/impuestos.
La revisión de precio mayorista debe evaluar combinación con promociones y cambios del precio base, y mostrar rango que incumpla el margen mínimo interno. No aplicar cambios a ML en esta etapa, aun cuando la recomendación parezca rentable.
No convertir automáticamente una lista interna mayorista, ni un transporte Vía Cargo, en venta B2B de Mercado Libre.

### Centralización propuesta: un expediente conectado, sin duplicar maestros

Objetivo de producto: desde una publicación o venta, recorrer su ficha/SKU y costo, precio minorista/mayorista, operación, envío, cobros, cargos y conciliación de MP con evidencia compartida. Cada módulo conserva su responsabilidad y los accesos navegan al mismo registro.
La pantalla nueva se apoya en Comercial; conciliación y control MP siguen vinculados a Administración/Tesorería y a las rutas ya existentes. Resolver menú y enlaces durante implementación sin duplicar pantallas por cada acceso.

| Proceso | Qué centralizar en Fierro | Base a reutilizar / dato adicional | Límite |
| --- | --- | --- | --- |
| Publicación | Estado, contenido, variantes, ficha e imágenes, diferencias, precio vigente y contexto B2B. Borradores de cambios revisables. | Catálogo/ficha, mapeos, observaciones y cola/propuestas comerciales existentes. | Lectura/contexto primero. Aplicar contenido/precio/pausa/stock requiere futura habilitación y validaciones por tipo de publicación; no promesa de edición universal. |
| Precio/costo | Costo histórico y actual separados, margen por tramo, cargos previstos/observados y explicación del cambio. | Costos versionados, listas, reglas, simulador y conciliación. | No crear segundo motor ni reemplazar rentabilidad real por precio sugerido. |
| Venta | Orden/líneas, pack, variantes, cantidad y contexto B2B, cancelación/devolución. | Pedido operativo por referencia y registro económico por línea. | Mantener identidades originales; proyección logística por SKU no es fuente de importes de todas las líneas. |
| Envío | Modalidad, bultos/datos disponibles, etiquetas, seguimiento, incidencias, costo cotizado/cobrado y responsable. | Integración de etiquetas y logística existente; shipments/costos y transportes propios según permisos. | Full no se activa; no equiparar ME2, Acordás y transporte externo. Datos ausentes no se completan por suposición. |
| Cobro | Pagos asociados, estado, devoluciones/contracargos y vínculos con orden/documentos. | Movimiento/venta observados, reportes autorizados y adaptador MP a verificar. | Pago aprobado, dinero liberado, saldo disponible y transferencia bancaria son hechos distintos. |
| Liquidación | Esperado frente a cargos/neto observado, fecha de liberación, notas de crédito y gastos tardíos. | Conciliación/cierres/legajo existentes y detalle de facturación ML. | Cargo y neto relacionados no impactan dos veces; reabrir revisión por nueva evidencia sin borrar el cierre anterior. |
| Cuenta MP | Reportes por cuenta/moneda/período; créditos, débitos, retiros, saldos documentados y partidas sin venta. | Adaptar importación actual por formato de reporte y enlazar con Tesorería offline. | Hace falta representación de movimientos de cuenta sin venta; no forzar el modelo actual ni escribir retiros reales. |
| Control | Excepciones, fuentes vencidas/faltantes, pendientes de vincular, diferencias y exportación. | Notificaciones, auditoría, cierres y controles compartidos. | No banners permanentes ni conciliación automática por importe/fecha solamente. |

Identidad transversal propuesta: organización + vínculo/cuenta externa + sitio; unidad asignada por vínculo validado; publicación + variante/unidad comercial; order_id + línea; pack_id; shipment_id; payment_id; movimiento/documento externo. IDs externos como texto, preservando valores alfanuméricos; nunca acoplarlos a un entero de 32 bits.
Una billetera MP puede contener actividad de varios canales/unidades. Conciliar saldo por cuenta real y luego asignar operaciones a la unidad correspondiente, con pendientes explícitos cuando no haya correspondencia. No copiar el mismo saldo total de cuenta en cada unidad y luego sumarlo.
Las referencias externas no se interpretan todas como order_id; una referencia de envío o retiro requiere su propio vínculo. El código de cuenta interno no sustituye validar dueño/seller/collector.
Capa de evidencia original sanitizada y versionada → normalización y clasificación → resultado/conciliación → presentación y propuestas. Evitar una segunda fuente de verdad y conservar exportaciones/huellas.
Para futura lectura conectada: adaptador central ML/MP, permisos verificables por cuenta/recurso, límites de consulta, paginación y reintentos acotados; evento como aviso seguido de lectura del recurso autorizado, no verdad financiera por sí solo. Jobs grandes fuera del request de pantalla, sin nuevos schedulers paralelos.
Para futura escritura conectada: vista previa del cambio exacto, revisión, comprobación de que la fuente no cambió, registro idempotente, resultado y auditoría. No activar nuevas suscripciones, publicaciones, reembolsos, retiros ni emisión fiscal por registrar este plan.

### MP: recursos documentados y frontera del control de cuenta

- MP publica reportes de Liquidaciones/Liberaciones, Dinero en cuenta y Actividades. Cubren perspectivas distintas; no se concatenan como si cada fila fuera otro cobro.
- Dinero en cuenta utiliza la familia /v1/account/settlement_report. Su API permite solicitar generación asíncrona, listar y descargar archivos. Release report utiliza /v1/account/release_report para la perspectiva de liberaciones; conservar tipo de reporte y versión de columnas al importar.
- El recurso de listado/descarga no garantiza que todos los campos necesarios hayan sido configurados ni que el reporte abarque toda la cuenta. Antes de interpretar saldo, comprobar período, moneda, alcance, filas de saldo y configuración.
- En reportes pueden aparecer referencias de orden/envío/operación y tipos como retiro o contracargo. Guardar identificadores y vínculo de origen, sin tratarlos como nuevas ventas. Fechas de movimiento, venta y liberación requieren ejes separados.
- Pagos específicos y búsquedas (/v1/payments/{id}, /v1/payments/search) son recursos candidatos, sujetos a autorización de esa cuenta/producto. No se acredita que la credencial ML actual permita acceder a toda la cuenta MP ni al historial completo.
- No se ha verificado un endpoint de saldo universal para Fierro. Saldo disponible/retenido/a liberar deben mostrarse solo si existe fuente que cubra cada concepto, con corte y origen. Si solo hay movimientos parciales, mostrar saldo calculado parcial y diferencia, no saldo bancario confirmado.
- Generar un reporte o configurar su periodicidad requiere llamadas externas, algunas POST. No se ejecutan en laboratorio ni se etiquetan como lectura sin efecto por no mover dinero. Inicialmente se ensaya con archivos sintéticos.

Control de consistencia propuesto para una misma cuenta/moneda/alcance/período: saldo inicial documentado + créditos que afectan ese saldo − débitos que afectan ese saldo = saldo final documentado. No sumar venta + liquidación + liberación del mismo ingreso como tres entradas; no sumar saldos de distinto alcance (disponible y total) como cuentas independientes.
Separar: dinero pendiente de liberación, dinero disponible documentado, reservas/bloqueos documentados, retiros y transferencias, cargos/impuestos, partidas no clasificadas. Ausencia de fuente => no disponible.
Movimientos sin referencia comercial se admiten en la futura capa de cuenta sin crear una venta ficticia; adaptaciones de esquema tienen su revisión y migración, sin levantar las barreras offline de Tesorería.
Importación: conservar tipo/período/cuenta/archivo/huella; reimportación exacta idempotente; solapamientos entre reportes se vinculan por hecho económico y fuente, no solo por payment_id (un pago puede tener cargos, devolución y liberación distintos). No borrar hechos tardíos para igualar saldos.
El lector de extractos actual reconoce un conjunto de encabezados y normaliza a liquidacion_neta; no debe aceptar silenciosamente un reporte de cuenta completo que requiera tipos y referencias diferentes.

Referencias oficiales MP:
- Tipos de reporte: https://www.mercadopago.com.ar/developers/es/docs/reports/introduction
- Generación/listado/descarga de Dinero en cuenta: https://www.mercadopago.com.ar/developers/es/reference/settlements-report/create-report/post ; https://www.mercadopago.com.ar/developers/es/reference/settlements-report/query-report/get ; https://www.mercadopago.com.ar/developers/es/reference/settlements-report/download-report/get
- Liberaciones y campos: https://www.mercadopago.com.ar/developers/es/docs/reports/released-money/api ; https://www.mercadopago.com.ar/developers/es/docs/links-and-debts/additional-content/reports/released-money/report-use
- Tipos de movimientos de cuenta: https://www.mercadopago.com.ar/developers/es/docs/mp-point/resources/reports/account-money/how-to-use
- Pagos: https://www.mercadopago.com.ar/developers/es/docs/subscriptions/additional-content/payment-management
- Etiquetas ME2: https://developers.mercadolibre.com.ar/es_ar/es_ar/mercadoenvios-modo-2
- Notificaciones: https://developers.mercadolibre.com.ar/api-docs/productos-recibe-notificaciones
Nuevas funciones conectadas se revalidan contra documentación y permisos al implementarlas; documentos de otros productos/sites no acreditan cobertura específica de Fierro.
La documentación reciente señala cambios en shipments (header y referencias retiradas) y ME1 V2; revisar únicamente consumidores aplicables antes de ampliar, sin modificar el flujo estable por anticipado.

### Priorización dentro de la construcción actual

1. PML-0: cerrar contrato económico, identidad de líneas/pack/cuenta y ensayos de rentabilidad offline. Incorporar clasificación B2B, tramos y formatos MP como entradas del contrato.
2. PML-1A: rentabilidad prevista/observada por venta y publicación, minorista y mayorista donde haya evidencia; costo histórico, embalaje, envío/cargos y estado de completitud.
3. PML-1B: extender el control MP existente a reportes de cuenta y liberaciones, enlazando cierres/Tesorería sin convertir proyecciones en operaciones reales. Filtros B2B/B2C/no determinado y detalle de diferencias.
4. PML-2/3/4: revisión de publicaciones, competencia e IA conservan el orden y condiciones anteriores. La ficha única y el estado financiero se navegan desde el mismo expediente.
5. Operación conectada futura: validar accesos de lectura de cuentas ya autorizadas en una etapa separada, después de aprobar offline. Gestión externa de contenido, precios por cantidad, promociones o stock se habilita por función, no por encender todo el canal. No incluye operar dinero ni habilitar Full automáticamente.

El objetivo no es reproducir todas las pantallas de ML/MP, sino resolver en Fierro la mayor parte del trabajo cotidiano con trazabilidad y enlaces al origen para excepciones. Criterio de cobertura por tarea: disponible con evidencia, parcial, requiere gestión externa o no habilitada; no prometer centralización del 100%.

### Casos adicionales de UAT a implementar (no ejecutados)

| Caso | Resultado exigido |
| --- | --- |
| PML-UAT-13 | Cuenta/publicación sin elegibilidad B2B o permiso desconocido: estado no disponible/pendiente, sin activación ni tabla mayorista ficticia. |
| PML-UAT-14 | Tramos B2B y precio vigente que cambia por promoción/base: simular límites inferior/exacto/superior, mantener versión y margen por tramo; descuento compuesto, no suma automática de porcentajes. |
| PML-UAT-15 | Una unidad comercial tipo pack frente a varias unidades de una publicación: cantidad comercial y costo físico correctos; no aplicar tramos sobre número físico inferido. |
| PML-UAT-16 | Beneficio de envío/cargo fijo no acreditado: no asumir ahorro ni cargo cero. Recomendación ML contrastada con costo/embalaje propios. |
| PML-UAT-17 | Snapshot legado de precios absolutos y tabla porcentual: lectura histórica explicada, no escritura nueva por endpoint obsoleto. Rechazar funciones exclusivas de otro site y no tratar B2C restringido como B2B general. |
| PML-UAT-18 | Misma operación en venta, facturación, extracto y liberación: cada hecho impacta una sola vez en su dimensión; cargos/devolución/liberación del mismo pago siguen como eventos distintos. |
| PML-UAT-19 | Retiro o transferencia sin venta: clasificar movimiento de cuenta sin forzar VentaCanalItem; no alterar rentabilidad del producto por retirar dinero. |
| PML-UAT-20 | Saldo inicial/final y créditos/débitos por período: ecuación consistente o diferencia visible; distinguir saldo total de disponible y de proyección de Tesorería. |
| PML-UAT-21 | Reportes solapados, evento tardío, archivo incompleto, moneda distinta o referencia alfanumérica: no duplicar, conservar corte/versiones, no marcar cobertura total. |
| PML-UAT-22 | Billetera con varias unidades/canales: saldo de cuenta contado una sola vez; asignación comercial validada, pendientes sin asignación y sin mezclar tenants. |
| PML-UAT-23 | Día argentino con cambio de fecha UTC: filtros y totales correctos según eje venta/movimiento/liberación; mostrar zona local conservando instante original. |
| PML-UAT-24 | Generación de reporte, cambio de PxQ y actualización externa simulados: barreras de red intactas; no crear jobs, conexiones, cobros, retiros, publicaciones ni efectos durante el UAT. |

Se conservan PML-UAT-01 a 12 y todos los pendientes previos. Este bloque no declara implementado ni aprobado ninguno de los casos nuevos.

### PML-0A implementado: ensayo de resultado por línea — 18/10/2026

- Base de implementación: 1ce5c77009988175267b0aba742e6316472675ae. El usuario indicó avanzar después de aprobar el plan y confirmar el cálculo de precio según objetivo.
- Nuevo servicio puro services/rentabilidad_ml_offline.py. Contrato v1 por operación/pack con contexto organización/unidad/cuenta, moneda ARS, corte con zona horaria, líneas originales, costo histórico identificado y previsión congelada, cobertura y hechos normalizados. Sin DB, red ni escrituras.
- Reutiliza conciliar_venta para la conciliación financiera. Los ejemplos usan liquidar_precio y calcular_precio_minimo_canal existentes; no se crea otro motor de precios. El objetivo mostrado en Venta simple/Neto es un recargo ilustrativo del 20% sobre producto y embalaje, explícitamente distinto de margen sobre venta; no cambia la configuración comercial real.
- Mantiene orden/publicación/línea aunque el SKU se repita. Gastos compartidos se reparten proporcionalmente al ingreso por mayor resto, conservando cada centavo y mostrando que son asignaciones. El total de envío no se multiplica por unidad.
- Resultado económico = ingreso efectivo y ajustes − costo histórico − gastos identificados. Neto de cobro se presenta aparte. El neto reemplaza bruto y cargos ya contenidos solo dentro de sus líneas; una mezcla de bruto con neto de alcance parcial se rechaza. Dos fuentes del mismo hecho coincidentes se vinculan sin sumarse; importes incompatibles se rechazan para revisión.
- Falta de costo da no_calculable, sin reemplazo por cero/costo actual. Fuentes/cobertura incompletas, estimaciones, diferencia entre cobro y reconstrucción o retención sin clasificación dan parcial. Cero confirmado es distinto de cobro ausente. Costo que ya incluye embalaje no admite otro débito de embalaje. Pérdidas y previsiones negativas se conservan; ingreso cero no produce margen inventado.
- Huellas de entrada/resultado permiten comprobar reproducción; son controles de integridad, no firma ni autorización del contenido.
- Nuevo blueprint GET /admin/comercial/rentabilidad-ml. Usa login, resolver_tenant_usuario y membresía admin, exige unidad activa de la organización y no selecciona una unidad ajena como fallback. La query no cambia contexto ni cuenta. No tiene POST, importación de archivos, selección de cuenta real ni efectos.
- Acceso agregado al panel Comercial existente: Rentabilidad ML · Ensayo offline. No se modifica sidebar ni menú global. La vista extiende base.html y reutiliza CSS/JS de paneles y diálogos; resumen compacto, tabla contenida, detalle modal, cierre sin envío y exportación JSON de entrada/resultado. Solo CSS específico nuevo para métricas y cobertura.
- Siete ejemplos internos: venta simple, cuatro órdenes con SKU repetido, neto/cargos repetidos, publicidad pendiente, costo histórico faltante, precio B2B ya aplicado y devolución parcial. Todos son sintéticos. No crean productos, ventas, cuentas, movimientos ni registros.
- Resultados de referencia: Venta simple, ingreso $10.000, costo $4.000, comisión $1.500, envío $1.000 y embalaje $300: resultado $3.200, margen 32%, neto $7.500. Pack: cuatro órdenes, cinco unidades comerciales, ingreso $54.000, envío único $4.000 y resultado $20.400. B2B sintético: cinco unidades a $8.550, resultado $12.837,50; no se re-aplican los descuentos al precio ya efectivo. Devolución parcial de $2.500: resultado $700, sin recuperar costo/reponer stock automáticamente.
- Verificación local: 83 pruebas focalizadas aprobadas de servicio, Flask y motores existentes; una prueba estática preexistente que lee app.py quedó fuera de la selección local de archivos. Se probaron cálculos independientes, pérdidas, neto/bruto/detalle, fuente repetida/incompatible, alcance parcial, costo histórico/faltante/fuera de fecha, embalaje duplicado, ceros, contexto/rol/unidad ajenos, importes inválidos, endpoints GET/exportación, reproducibilidad/huellas y efectos cero.
- Compilación Python y parseo completo de las dos plantillas aprobados. Render de las siete vistas mediante Flask; comprobados IDs de modales únicos, detalles cerrados, sin formularios anidados y retorno type=button. El navegador headless no pudo instalarse por descarga incompleta; no se afirma inspección visual automatizada ni prueba real de teclado contra Render.
- Sin cambios de modelos, migraciones, app.py, domain.estados, datos, credenciales, permisos, flags, scheduler, webhooks ni producción/main.

Alcance pendiente, conservado del plan:
- No es todavía importación/conciliación de ventas reales ni adaptador de respuestas de la API. El contrato recibe hechos offline ya normalizados; no acredita por sí solo propiedad/elegibilidad de una publicación externa.
- El ejemplo B2B usa un precio efectivo sintético conocido. Elegibilidad, lectura/selección/versionado de tramos, recomendaciones ML, promociones cofinanciadas y migración de cardinalidad siguen pendientes.
- Faltan conectores, tratamiento completo de saldo de cuenta MP/reportes solapados/movimientos sin venta y recuperación de costo por devoluciones. No se declara resuelto el conjunto PML-UAT-01 a 24 por tener ejemplos.
- La liquidación prevista se recibe congelada; el ejemplo descuenta una sola vez el envío compartido. No se cambia el motor anterior que calcula una expectativa por unidad, ni se aplica ese comportamiento sin normalizar al nuevo circuito.
- El precio objetivo de referencia se muestra solo con fuentes completas en esos ejemplos; la adaptación del objetivo de precio a tramos/pack y métodos de margen requiere la etapa siguiente. La función actual de cálculo de precios existente se conserva.

Próximo UAT tras deploy:
1. Abrir Comercial → Rentabilidad ML · Ensayo offline, con unidad Ensayo UAT.
2. Seleccionar Venta simple y pulsar Analizar ejemplo. Debe verse feedback, resultado $3.200, margen sobre venta 32%, diferencia $0 y liquidación $7.500; detalle contiene comisión/envío/embalaje y costo histórico.
3. Abrir/cerrar Ver detalle mediante Cerrar/X/Escape, sin cambios ni guardado; revisar presentación y sidebar.
4. Descargar evidencia del ensayo y verificar huellas/alcance. Después pasar a Pack, Neto repetido y ejemplos de fuentes faltantes; no repetir altas previas ni subir archivos reales.
Este bloque sí requiere deploy de integración para revisar la pantalla. Mantener laboratorio desconectado; no hacer deploy de producción.

### PML-0A: evidencias de los siete ejemplos y ajustes de presentación — 19/10/2026

Base desplegada del bloque: a195b76be9f47ffc4b29bf0f54325f498ff0b03e (referencia del código; las capturas no acreditan por sí solas el SHA ejecutado en Render).
Se revisaron las siete exportaciones aportadas por el usuario. Ambas huellas canónicas de entrada y resultado coinciden en cada archivo. Contexto organización 1 / unidad 3 / cuenta sintética. Los controles de los documentos declaran persistencia false y conexiones, stock, pagos y publicaciones en cero; no son una auditoría independiente del servidor.

| Evidencia | Resultado comprobado | Huella del resultado |
| --- | --- | --- |
| rentabilidad_ml_ensayo_simple.json | $3.200; 32%; neto $7.500. Modal con costo histórico y comisión/envío/embalaje. | a73b5b14138eca5227347c92976bb79189f25eed31a48de26ef3c717579a95ef |
| rentabilidad_ml_ensayo_pack.json | Cuatro órdenes, cinco unidades, SKU repetido con precios diferentes. Envío único $4.000, reparto exacto; resultado $20.400, neto $41.900. | b35f4cb1e5efbc8f9474e5edc9c124b3c24db382d393913e2b783b3b688b0dd4 |
| rentabilidad_ml_ensayo_neto.json | Una fuente duplicada vinculada sin sumarse. Comisión única $1.500; resultado $3.200, neto $7.500. | 16b01dfd01101c3a2d92c42470ed8a615078af471256cfb6b80cc8ee19b48a44 |
| rentabilidad_ml_ensayo_faltantes.json | Estado parcial, publicidad pendiente; $3.200 solo con conceptos conocidos. Avisos amarillos visibles. | 5cb34da858387cab89614fc1ef5847f7872af0a6297c330ca211ceed11701399 |
| rentabilidad_ml_ensayo_sin_costo.json | no_calculable: costo, ganancia, margen y objetivo null. Sin captura aportada para este caso. | 97cd209dd675e26f227215f445bb5471ce6a5bc1038a024cab1529ea92dbdf3d |
| rentabilidad_ml_ensayo_mayorista.json | Cinco unidades a $8.550 efectivos. Descuentos no restados nuevamente; resultado $12.837,50, margen 30,03%, neto $34.337,50. | 1cb744da07cdcfbf31e6093a234c109745a13ba28de8e0ba1d069a058fd17c68 |
| rentabilidad_ml_ensayo_devolucion.json | Reintegro $2.500, costo original $4.000; resultado $700, margen 9,33%, neto $5.000. Sin recuperación automática de costo/stock. | 22103847eda0ebbee697f5004801af8ccf0251e6620a55f9acd12a2c0fba0f2d |

Ajustes realizados tras este UAT:
- Margen con coma decimal en HTML; el dato decimal canónico del JSON no se modifica.
- Se elimina únicamente el contorno de foco del contenedor #resultado, conservando tabindex, salto al resultado e indicadores de foco de los controles.
- criterio_objetivo queda null cuando no se calcula precio objetivo. Corrige la descripción contradictoria de publicidad no aplicable en Gastos pendientes y evita describir un objetivo inexistente en otros casos. Los archivos anteriores conservan sus huellas y no se reescriben; futuras descargas actualizan ese metadato externo a entrada/resultado.
- Cache de CSS actualizada para que Render solicite la versión nueva.
- Verificación de esta corrección: compilación Python, render Jinja de las siete evidencias con layout mínimo de prueba y filtro monetario, coma decimal, null y visibilidad condicional del objetivo. Sin cambios en el motor ni repetición de las 83 pruebas del bloque original. No se afirma prueba de navegador/teclado o DB de Render.

Estado: siete casos sintéticos comprobados en evidencia; queda revisar estos ajustes visuales después del deploy. El modal se vio abierto en captura; Cerrar/X/Escape y sidebar completo no quedan acreditados individualmente por estas capturas.
No valida ventas reales, elegibilidad B2B, lectura de tramos, reportes MP ni el conjunto PML-UAT-01 a 24. Se mantienen las limitaciones y pendientes anteriores, producción fuera de alcance y laboratorio desconectado.
Próximo bloque seguro propuesto: ingreso offline de evidencia normalizada con vista previa y validación de organización/unidad/cuenta/moneda/corte, sin guardar ni consultar ML/MP. Reutilizar este contrato, los costos y la conciliación existentes; no crear otro catálogo ni motor.

### PML-0B: carga transitoria de evidencia normalizada — 19/10/2026

Continuación autorizada por el usuario tras verificar los ejemplos. Base: ee5da1236badf051114855a5f89fc9a85cf0cc82.
Las capturas image(20261019-124159).png y image(20261019-124300).png acreditan margen 32,00%, resultado $3.200, contenedor sin borde negro y referencia $7.248 por unidad con aclaración de recargo del 20% sobre costo. No se repitieron las siete altas/ensayos ni se infiere el SHA de Render solo por la imagen.

Implementación:
- Se agrega un formulario plegado en la misma pantalla: Analizar un archivo offline. Admite JSON UTF-8 (también BOM) hasta 2.000.000 bytes: contrato v1 o exportación con entrada. No usa respuestas crudas de ML/MP.
- Reutiliza analizar_rentabilidad y la conciliación existente. Si el archivo contiene resultado/escenario, se ignoran y se recalculan; no se consideran evidencia confiable ni se utiliza un precio objetivo precargado. Una huella reproducible no acredita autenticidad externa.
- Alcance de cuenta deliberadamente limitado a demo-rentabilidad-sin-conexion, organización del admin y unidad activa válidas en sesión. No se infiere cuenta confiable desde el archivo ni se habilitan cuentas reales. La moneda y fechas/corte/costo se validan con el contrato existente.
- Nueva ruta POST /admin/comercial/rentabilidad-ml/archivo, protegida por login, rol y CSRF global existente, sin exenciones. Las rutas GET de ejemplos y exportaciones anteriores se conservan. No hay alta/confirmación de operación.
- El navegador envía los bytes del archivo como application/json con cabecera X-CSRF-Token; la ruta lee un máximo acotado del stream. No usa multipart/request.files, guardado de adjuntos, DB, sesión de resultados, localStorage ni conexiones ML/MP. Respuestas del blueprint no-store y nosniff.
- Resultado en la misma pantalla, con foco/salto al resultado y modales compartidos. Texto de archivo distingue datos declarados de fuentes externas verificadas. Avisos de rechazo usan la presentación existente; no se muestra un resultado anterior como si el archivo rechazado fuera válido.
- Botón Analizar archivo bloqueado durante lectura, aviso Analizando archivo, Cancelar aborta la petición y descarta respuestas tardías. Cancelar no guarda. La carga y descarga local requieren JavaScript.
- Descargar evidencia recalculada genera rentabilidad_ml_archivo_recalculado.json mediante Blob local con entrada y resultado recalculados y metadatos del servidor, sin solicitar otra operación. El archivo permanece en la memoria de la pestaña mientras está visible; recargar/navegar descarta el resultado transitorio.
- Se rechazan JSON inválido/no UTF-8, claves duplicadas, NaN/infinito, exceso de tamaño/profundidad, tipos anidados inválidos y contextos ajenos. Un archivo válido con fuente/costo faltante conserva parcial/no_calculable; no transforma ausencia en cero.

Verificación:
- 97 pruebas focalizadas aprobadas (60 existentes de servicio/rutas + 37 casos nuevos parametrizados de archivos/rutas). Incluye los siete escenarios recalculados, ignorar totales falsos, escaping de HTML/JSON, permisos/unidad/organización/cuenta/moneda, tamaño/tipos/fechas, BOM, ausencia de persistencia y CSRF. El test de CSRF ejecuta la función real extraída de app.py sin modificarla; el fixture no inicia toda la aplicación.
- Compilación Python y node --check aprobados. Ensayo JS con DOM/fetch mínimos verificó rechazo de tamaño antes de enviar, POST JSON/CSRF, estado ocupado y Cancelar impidiendo reemplazo tardío. No sustituye un navegador real.
- Sin cambios de motor, modelos, migraciones, app.py, bootstrap, sidebar, scheduler, permisos externos, flags, datos ni producción. No se declara validada rentabilidad real ni resueltos B2B/tramos/reportes MP/cuentas reales, y permanecen los pendientes previos.

Próximo UAT en staging tras deploy:
1. Comercial → Rentabilidad ML · Ensayo offline → desplegar Analizar un archivo offline.
2. Seleccionar el archivo ya disponible rentabilidad_ml_ensayo_simple.json y tocar Analizar archivo. Debe mostrar $3.200, 32,00% y liquidación $7.500; título Archivo offline y aviso de datos declarados.
3. Abrir/cerrar Ver detalle y descargar evidencia recalculada para verificarla. No hace falta reconstruir ni editar el JSON de prueba.
4. Comprobar Cancelar antes del envío: restablece el selector y cierra el formulario sin registrar operaciones. Rechazos técnicos ya cubiertos localmente; los avisos y descarga requieren revisión real de navegador.

### PML-0B validado en UAT y PML-0C: lectura de snapshots ML — 19/10/2026

Cierre acotado de PML-0B:
- Captura image(20261019-131755).png: archivo DEMO-SIMPLE analizado, $3.200, margen 32,00%, neto $7.500 y etiquetas de datos declarados.
- rentabilidad_ml_archivo_recalculado.json aportado: entrada y resultado idénticos a rentabilidad_ml_ensayo_simple.json. Ambas huellas canónicas válidas; huella del resultado a73b5b14138eca5227347c92976bb79189f25eed31a48de26ef3c717579a95ef. Cambian solo metadatos de presentación, sin precio objetivo importado.
- Cancelar antes del envío: el usuario confirmó el comportamiento solicitado (cierre y selección limpia, resultado previo conservado). No acredita por sí solo todas las carreras de red o teclas del navegador.
- Captura image(20261019-132107).png: DEMO-FALTANTES conserva $3.200 identificados como parciales; aviso amarillo y publicidad pendiente. No se recibió otra exportación de este caso por la carga nueva.

Base de PML-0C: ee2792e6ac66db74ac091455bcf18a552cdec681.
Auditoría de reutilización:
- Se reutiliza adaptar_fixture de services/adaptadores_offline_canales.py para las líneas de venta, luego de exigir cantidad/precio/moneda válidos. No se usa el normalizador legado de comisiones de publicación ni sus ceros por ausencia.
- El lector operativo ml_pack_items agrupa por SKU y filtra estados; se conserva intacto y no se usa para reconstruir historia financiera. Importación de conciliación escribe registros y consulta costos vigentes: tampoco se llama en este circuito transitorio.
- Resultado y conciliación siguen siendo los existentes; no se crean catálogo, maestro de publicaciones, motor de precios ni libro MP paralelos.

Contrato de archivo nuevo (envoltorio propio, no respuesta literal de un endpoint):
- formato = ml_rentabilidad_offline_v1; organización/unidad/cuenta y fecha_corte; seller_id declarado.
- pack opcional con id y orders; ordenes contiene respuestas con id, status, seller, contexto MLA, moneda ARS, date_created y order_items; shipping.id identifica alcance si está disponible.
- publicaciones contiene snapshots por id/vendedor/moneda, con título solo referencial. Su precio actual no sustituye unit_price histórico ni se utiliza para margen.
- datos_locales enlaza costo_snapshot y previsión por order_id + posición original (referencia_linea desde 1), declara cobertura, gastos previstos, hechos complementarios y cargos_ml_incluidos_en_neto (booleano obligatorio). El archivo original y esa posición deben conservarse; reordenamientos de order_items requieren otra revisión.
- costos_envio reúne shipment_id, fecha y respuesta del recurso de costos. Se toma únicamente el costo del vendedor declarado, una vez por envío y con sus líneas; receiver.cost y gross_amount no se imputan al vendedor.
- Los cobros/netos y gastos complementarios siguen entrando como hechos normalizados existentes. No se adapta todavía una respuesta cruda de MP ni facturación de cargos finales. paid_amount/payments de orden no generan neto ni acreditan disponibilidad.
- Se rechaza un hecho complementario de comisión/envío que intentaría duplicar lo extraído de esos snapshots. La relación con el neto se declara expresamente y las diferencias siguen visibles en conciliación.

Implementación y límites:
- services/lectura_ml_rentabilidad.py traduce a contrato v1, conservando orden, posición, publicación, variante, SKU, cantidad y precio. Se valida manifiesto completo sin órdenes repetidas/ajenas, vendedor, sitio y moneda declarados. No acredita propiedad ni autenticidad externa.
- Solo status paid; canceladas/invalid/devoluciones no se omiten silenciosamente, se rechazan para revisión. El contrato normalizado anterior conserva sus casos de devolución; la traducción de estados ML restantes sigue pendiente.
- sale_fee se interpreta por unidad. Ausencia queda pendiente; cero explícito se conserva. Importes negativos/no finitos/fuera de rango o con fracción de centavo no se redondean para aceptar datos inválidos.
- Si hay indicios de descuento en discounts/gross_price, se marca descuentos pendiente sin volver a restarlos del precio efectivo. Cofinanciación, compensaciones y detalle de promociones requieren etapa adicional.
- Sin costo histórico se conserva no_calculable. Sin costo de envío/fee/cobro se conserva parcial. Los costos/previsiones locales son declarados y no se reemplazan por el costo o regla actual de DB.
- Trazabilidad en entrada: huella canónica del snapshot declarado, vendedor, pack, clasificación B2B/no determinado por orden y publicaciones referenciales. No se exportan compradores, direcciones, pagos crudos ni credenciales a la entrada normalizada. La huella no es firma ni prueba de titularidad.
- B2B solo indica contexto/tags declarados. No acredita elegibilidad, tramos ni precios por cantidad; ausencia de b2b se muestra no determinado, no B2C por defecto.
- El mismo formulario acepta ambos contratos y exportaciones previas. Se incorpora Descargar ejemplo ML · Pack de cuatro órdenes, generado en contexto activo por GET; no requiere confeccionar archivos ni ZIP.
- Resultado usa la misma vista/modales, con origen y alcance ML plegados y huella que ajusta al ancho. Cuenta sigue limitada a demo-rentabilidad-sin-conexion; mismo límite de 2 MB, CSRF, memoria transitoria, no-store y sin persistencia.
- El ejemplo reutiliza los datos del pack ya aprobado: 4 órdenes, 5 unidades, ingreso $54.000, comisión $8.100, envío $4.000, embalaje $1.500, costo $20.000; resultado $20.400, margen 37,78%, neto $41.900. price actual de publicación $99.999 y receiver.cost $9.999 son deliberadamente distintos y no se usan en ese cálculo.

Verificación final: 135 pruebas focalizadas aprobadas (97 previas y 38 casos nuevos parametrizados). Incluyen cuatro órdenes/SKU repetido/precios distintos, varias líneas y variantes, alcance de dos envíos, fee por unidad, importes extremos, faltantes y ceros, contexto/moneda/estado/vendedor ajenos, coherencia del manifiesto, descuentos pendientes, relación con neto, relectura de exportación normalizada sin reaplicar cargos, GET de ejemplo y POST de archivo/render/rechazo. Compilación Python aprobada. No se realizó inspección visual de navegador ni prueba con API/DB reales para esta traducción.

Documentación oficial consultada 19/10/2026 para los campos y sus límites:
- Órdenes: https://developers.mercadolibre.com.ar/es_ar/metricas/gestiona-ventas
- Tarifa por unidad y separación de orden/pack/envío: https://developers.mercadolibre.com.ar/es_ar/envio/provisiones
- Costos por usuario en senders y receiver: https://developers.mercadolibre.com.ar/es_ar/envios
La consulta de documentación no llamó a cuentas ML/MP ni habilitó conexiones. Cambios de formatos/permisos conectados se revalidan antes de su futura implementación.

Pendientes conservados: lectura de cuentas reales/autenticación externa, vínculo de envíos que no venga en la orden, normalización de facturación final ML, pagos/reportes/cuenta MP completos, elegibilidad/tramos/promociones cofinanciadas, resto de estados de orden y conciliación de devoluciones ML. Se mantienen PML-UAT-01 a 24 y pendientes de otros módulos; este lector no los declara resueltos.
Sin modificaciones de app.py, modelos, migraciones, estados operativos, sincronizador de packs, scheduler, webhooks, flags, credenciales, permisos externos ni producción.

Próximo UAT tras deploy de integración:
1. Comercial → Rentabilidad ML · Ensayo offline → Analizar un archivo offline.
2. Descargar ejemplo ML · Pack de cuatro órdenes. Seleccionar ese rentabilidad_ml_snapshot_pack_demo.json en el mismo formulario y Analizar archivo.
3. Verificar Snapshot ML offline, cuatro filas/cinco unidades, $20.400, 37,78% y neto $41.900; abrir Ver detalle y Origen y alcance del archivo ML.
4. Descargar evidencia recalculada para comprobar huellas, fuentes y envío único. No se repiten las siete pruebas anteriores ni se usan datos reales.


### PML-0C validado en UAT y PML-0D: contraste MP offline — 19/10/2026

Cierre acotado de PML-0C:
- image(20261019-141921).png y rentabilidad_ml_archivo_recalculado (1).json: cuatro órdenes originales, cinco unidades, SKU repetido con precios históricos distintos, ingreso $54.000, costo $20.000, comisión $8.100, envío compartido $4.000, embalaje $1.500, resultado $20.400, margen 37,78%, neto $41.900 y diferencia cero.
- Huellas canónicas de entrada/resultado válidas. Resultado: 061cc7cb5244c2f9f0f8174379896c6eaf768de0b2c6f8ca8d9cf68de2a5dd96. Snapshot ML declarado: cc64b469ec18de62b56d504674c4de9e6b541fef2dc758c9bb036d4858ff94ee.
- Envío único ml-envio:DEMO-SHIP-1 repartido en 400000 centavos, cinco hechos económicos de cargos ML y todos los controles de ejecución/persistencia en cero.
- image(20261019-142022).png: origen y alcance desplegados, vendedor/pack ficticios, cuatro órdenes con contexto mayorista No determinado y huella correspondiente. Presentación aceptada por el usuario. No se atribuye a estas capturas una prueba individual de Cancelar/X/Escape del modal.

Base de PML-0D: 493e657e120932755cebbcee7301ec251b0da9dd.
Alcance y reutilización:
- Nuevo lector puro services/lectura_mp_rentabilidad.py, sin DB/red, encadena el lector ML existente y el mismo motor de rentabilidad/conciliación. No crea otro maestro, cuenta corriente ni motor de gastos.
- Contrato propio ml_mp_rentabilidad_offline_v1: snapshot_ml, collector_id declarado y pagos_mp con respuesta de pago, órdenes vinculadas explícitamente, fuente del vínculo y relaciones entre índices fee_details y hechos ML. No es una respuesta literal de un endpoint.
- No se usa el adaptador legado _adaptar_pago_mp porque convierte neto ausente en cero; permanece sin modificar.
- Organización/unidad/cuenta siguen verificadas contra el contexto del servidor. Solo cuenta ficticia, ARS y pagos approved; operaciones distintas de regular_payment, reintegros conocidos, órdenes ajenas, pagos duplicados y alcances ambiguos se rechazan para revisión.
- No se infieren vínculos a partir de importes, external_reference ni order.id MP. Cobrador y vínculos son declarados, sin acreditar acceso ni titularidad externa.
- Neto ausente queda pendiente; cero explícito se conserva como cero. Se controla corte de aprobación/actualización y cobertura/bruto de las órdenes vinculadas. Se admiten varios pagos del mismo alcance sin solapamientos parciales ambiguos.
- Cargos del comprador no se imputan al vendedor. Cada cargo collector requiere relación explícita con hechos ML del mismo concepto; importes y alcance agregados deben coincidir. Se incorpora una fuente del mismo hecho para que la deduplicación existente no vuelva a restar el gasto.
- Diferencias de cargos no sobrescriben ML para forzar coincidencia; dejan resultado parcial. Cargos sin vínculo/responsable, charges_details sin clasificar, impuestos y cupones informados requieren revisión sin inventar importes. Faltantes de actualización, tipo de operación o devoluciones también dejan parcial.
- Extensión acotada del motor: pendientes_fuente opcional, validado y limitado, para conservar estos faltantes en el resultado. Ausencia del campo conserva el comportamiento anterior.
- Se rechaza mezclar netos/brutos normalizados previos con nuevos cobros MP del mismo paquete. Este lector exige declarar que los cargos ML están incluidos en el neto; otros alcances requieren tratamiento posterior.
- Entrada exportada conserva trazabilidad mínima y huella del paquete; no copia pagadores, tarjetas, domicilios ni credenciales. La huella comprueba integridad, no autenticidad.
- Un pago aprobado/net_received_amount no acredita saldo disponible, liberación ni transferencia bancaria. La pantalla muestra Saldo disponible: no consultado.

Interfaz y ejemplo:
- Mismo formulario plegado Analizar un archivo offline y mismo límite de 2 MB/CSRF/no-store/memoria transitoria. Nuevo enlace Descargar ejemplo ML + MP · Cobros y cargos, archivo rentabilidad_ml_mp_snapshot_demo.json en contexto activo.
- Ejemplo reutiliza las cuatro órdenes/cinco unidades ML, con cuatro pagos, cuatro comisiones y porciones de un único envío compartido. Neto total $41.900; resultado $20.400 y 37,78%. Los cinco hechos ML contrastados agregan fuentes sin otro descuento. Incluye cargos de financiación del comprador para verificar su exclusión.
- Contraste de cobros y cargos MP plegado, tablas contenidas con pagos y cinco grupos de cargos, diferencias y huella ajustada al ancho. Reutiliza clases visuales actuales, sidebar y modales; no agrega estilos ni controles paralelos.

Verificación:
- 178 pruebas focalizadas aprobadas: las 135 anteriores y 43 casos MP parametrizados, incluidos contexto ajeno, neto ausente/cero, duplicación, varios pagos por orden, fuentes/cobertura, responsables, cargos discordantes, devolución, fechas, estructuras/importes inválidos y GET/POST/render/exportación/rechazos.
- Compilación Python aprobada. Pruebas de rutas usan fixture y CSRF real extraído de app.py; no arrancan toda la aplicación. Sin prueba de navegador real, Postgres, API ni despliegue Render en este bloque.
- Sin cambios de modelos, migraciones, app.py, bootstrap, sidebar, sincronizador operativo, scheduler, webhooks, flags, credenciales, permisos externos ni producción. BOOTSTRAP_BASE_DATOS_HABILITADO=false y MODO_LABORATORIO_DESCONECTADO=true permanecen.

Documentación oficial consultada 19/10/2026:
- GET de pago y campos declarados: https://www.mercadopago.com.ar/developers/es/reference/online-payments/subscriptions/get-payment/get
- Ejemplo oficial con net_received_amount y fee_details/responsable: https://www.mercadopago.com.ar/developers/en/docs/resources-pci-compliant-merchants/unified-post
Estas referencias no verifican permisos o cobertura de las cuentas ML/MP de Fierro. No se llamaron cuentas de vendedores ni se habilitaron conexiones; charges_details y reportes se mantienen pendientes.

Pendientes conservados: cuentas reales/autenticación y alcance, reportes de cuenta/liberación/liquidaciones/retiros, cargos finales ML/MP y diferencias económicas, clasificación fiscal/retenciones/cupones/cofinanciación, devoluciones y contracargos, B2B/tramos y cálculo de precio por rentabilidad pretendida dentro del plan existente. Se mantienen todos los pendientes previos y de otros módulos.

Próximo UAT tras deploy de integración:
1. Comercial → Rentabilidad ML · Ensayo offline → Analizar un archivo offline.
2. Descargar ejemplo ML + MP · Cobros y cargos; seleccionar rentabilidad_ml_mp_snapshot_demo.json y Analizar archivo.
3. Verificar Snapshot ML + MP offline, resultado $20.400, margen 37,78% y neto $41.900.
4. Desplegar Contraste de cobros y cargos MP: cuatro pagos, cinco grupos coincidentes y Saldo disponible: no consultado. Descargar evidencia recalculada para comprobar importes/huellas y cargos únicos. No repetir los siete escenarios previos ni usar datos reales.


### PML-0D validado y UAT de faltantes/diferencias MP — 19/10/2026

Evidencia recibida del despliegue 855da1afabe0a8e24700aee3cdb018cb6213e8ba:
- image(20261019-144715).png: Snapshot ML + MP offline, cuatro órdenes/cinco unidades, resultado $20.400, margen 37,78%, diferencia prevista cero y liquidación $41.900.
- image(20261019-144802).png: cuatro pagos aprobados declarados, cinco grupos coincidentes con diferencia cero y Saldo disponible: no consultado. Tablas alineadas/contenidas y huella visible.
- rentabilidad_ml_archivo_recalculado (2).json: huellas canónicas de entrada y resultado válidas, recálculo idéntico al exportado y entrada idéntica al generador de ejemplo en organización 1/unidad 3.
- Huella de entrada: 912d0b8168c835d766ded469cdc47a057b0ee09a1d15373dd26e9432e99c0731.
- Huella de resultado: 6705017975882254a4cb8a77af7d3406e4622e0b52af1249cb02d2cb72f08ff1.
- Huella del paquete MP original reconstruido: 73ad8d004266b2532b29421ffd10402820981e082f7806f7998974b8cb9efbf2, coincide con captura/trazabilidad.
- Cuatro comisiones únicas ($8.100) y un envío único ($4.000), con dos fuentes por hecho. Cinco fuentes duplicadas no sumadas. Reparto del envío conserva exactamente 400000 centavos. Cobro neto total 4190000, resultado 2040000, controles de ejecución/persistencia en cero.
- Cierre limitado a datos sintéticos declarados; no acredita rentabilidad real, titularidad de cuentas ni saldo disponible. No amplía validación de teclas/cancelación.

Siguiente bloque acotado:
- Se extiende el generador MP existente con casos completo (sin cambios), sin_neto y cargo_diferente. No se incorpora otro motor ni se modifican lector, cálculos o estados operativos.
- En el formulario actual, Más pruebas MP · Faltantes y diferencias permanece plegado y ofrece dos descargas. No exige editar JSON. Casos desconocidos se rechazan con aviso del sistema.
- Neto pendiente: retira net_received_amount de los cuatro pagos conservando bruto/cargos; deben mostrarse netos Pendiente, liquidación observada Pendiente y resultado parcial $20.400/37,78%. No interpreta falta como cero o bruto.
- Cargo con diferencia: primera comisión MP $1.600 frente a $1.500 ML; primer neto MP $7.659,26. El neto total es $41.800, diferencia de cargo +$100 y diferencia de reconstrucción -$100. Resultado económico identificado $20.400/37,78% se conserva parcial, con grupo Requiere revisión; no se sobrescribe ML ni se agrega otro gasto para ocultar discrepancia.
- 183 pruebas focalizadas aprobadas (178 previas + 5 casos nuevos parametrizados): descargas/contexto, resultado parcial/avisos, netos ausentes, diferencia visible, exportación/relectura y caso inválido. Compilación Python aprobada. Sin prueba de navegador real para estas dos variantes.
- Sin cambios de CSS/JS, core, modelos, DB, credenciales, flags, conexiones externas ni producción. Todos los pendientes previos conservados.

Próximo UAT tras deploy:
1. Comercial → Rentabilidad ML · Ensayo offline → Analizar un archivo offline → Más pruebas MP · Faltantes y diferencias.
2. Descargar MP · Neto pendiente, seleccionar el archivo y Analizar archivo. Verificar aviso amarillo/Resultado parcial, faltantes de neto y liquidación observada Pendiente.
3. Descargar MP · Cargo con diferencia y analizarlo igual. Verificar Resultado parcial, neto $41.800 y, en Contraste de cobros y cargos MP, grupo 1 Requiere revisión con $100 de diferencia.
4. Captura y evidencia recalculada de cada variante para verificar el UAT. No repetir escenario completo ya validado.

### Alertas de rentabilidad — requisito explícito, pendiente de implementación

Consulta del usuario 19/10/2026: avisar automáticamente sobre publicaciones con rentabilidad inferior a la esperada. El precio objetivo no garantiza el margen posterior: costos, cargos, envíos, promociones y ajustes pueden variar. No se declara implementado ni activado un monitoreo por este registro.

Integración al plan vigente:
- Publicación: comparar margen previsto recalculado con objetivo/mínimo configurado por cuenta/canal; mostrar motivo, vigencia/fuente y gastos incluidos. Evaluar con costos actuales para decisiones futuras, sin reescribir costos históricos de ventas.
- Venta: comparar margen/resultado obtenido con la previsión congelada de esa operación y tolerancia a definir. Separar resultado económico de cobro neto/disponibilidad. Margen sobre venta no equivale a recargo sobre costo.
- Datos incompletos: alerta Rentabilidad pendiente de confirmar, sin afirmar cumplimiento del objetivo ni pérdida definitiva.
- Reutilizar los mecanismos existentes de notificaciones y control/conciliación, auditando antes su encaje; evitar otro centro paralelo. Prever agrupación por publicación/cuenta, deduplicación y actualización/resolución al cambiar la evidencia, sin avisos persistentes invasivos.
- Umbrales, tolerancias y frecuencia aún por definir/validar; no inventar un porcentaje global. Mantener visible el acceso al desglose para revisar causas.
- Ningún ajuste automático de precio, pausa de publicación ni conexión/notificación externa se autoriza por este requisito. La futura activación sobre cuentas reales requiere su etapa de integración/UAT.


### REGLA INSALVABLE — precio mínimo para alcanzar el neto definido en Fierro

Confirmada expresamente por Martín el 19/10/2026. Es requisito obligatorio de diseño, implementación y UAT; prevalece sobre ejemplos de recargo o margen que pudieran interpretarse como su sustituto.

**El precio a publicar debe ser el menor precio admisible que produzca un neto a percibir mayor o igual al mínimo definido en Fierro para el alcance de esa publicación/operación. No se permite aprobar ni presentar como válido un precio cuyo neto previsto quede por debajo de ese mínimo.**

Definiciones y cálculo:
- El mínimo a percibir es el valor definido en el sistema. No se reemplaza por un porcentaje arbitrario, un recargo sobre costo, el precio de un competidor ni el saldo disponible en Mercado Pago.
- La composición de ese mínimo debe quedar explícita: si ya incorpora costo del producto, embalaje u otros componentes, no volver a deducirlos. El neto y el mínimo se comparan con igual moneda, cantidad, alcance y tratamiento de gastos.
- Las comisiones y cargos variables dependen del precio final. Reutilizar el motor vigente y evaluar precios candidatos recalculando todos los cargos/gastos que correspondan a cada candidato, incluidos cargos fijos, envío a cargo del vendedor, descuentos/promociones asumidos por el vendedor, cambios de tramo y redondeos.
- Buscar el menor precio admisible que satisface neto(precio) >= mínimo_a_percibir. No aplicar un colchón arbitrario que encarezca de más ni suponer una función continua/monótona al cruzar tramos sin validarlo. La estrategia de búsqueda debe contemplar esos cortes y la precisión/paso permitido del precio.
- Verificar nuevamente el precio final y su desglose con los mismos criterios de cargos y redondeo. La aproximación no puede justificar un neto inferior al mínimo; el candidato inmediatamente inferior admisible debe incumplir o existir evidencia equivalente de minimalidad en los tramos evaluados.
- Si el precio mínimo viable resulta poco competitivo, mostrar el conflicto para decisión comercial. No bajar silenciosamente el mínimo ni publicar por debajo para acompañar el mercado.
- Si faltan costos/cargos, vigencia o cobertura, mostrar estimación pendiente de validar y bloquear su aprobación como precio que cumple el mínimo. No llamar asegurado a un cálculo con fuentes incompletas.
- El cumplimiento calculado corresponde al alcance y datos vigentes utilizados; no garantiza que una liquidación futura carezca de ajustes. Las alertas posteriores contrastan lo previsto con lo efectivamente percibido y detectan desvíos, sin sustituir esta validación previa.
- Persistir/reproducir, cuando corresponda esa etapa, mínimo aplicado, precio final, cargos incluidos, fuentes/vigencia y versión del cálculo para explicar la decisión. Los ensayos actuales siguen transitorios y desconectados.

Criterios obligatorios de aceptación futura: igualdad exacta del neto mínimo; candidato inferior que no cumple; redondeo al centavo/paso permitido sin quedar por debajo; límites y saltos de tramos; gastos incluidos una sola vez; faltantes que impiden declarar cumplimiento; precio viable fuera de mercado sin rebajar el mínimo; conservación de la previsión histórica para contraste posterior.

Estado: regla registrada, pendiente completar su implementación y UAT en el cálculo de precio objetivo reutilizando lo existente. No se declara resuelta por el simulador de recargo ni por los ejemplos de rentabilidad. Este registro no modifica producción ni habilita publicaciones, cambios de precio o conexiones externas.


### Prioridad: terminar dependencias antes del producto integral — 19/10/2026

Martín solicita agrupar cambios por circuito y reducir rondas de pruebas aisladas. Aclara que primero deben completarse los módulos necesarios y después cargar un producto de prueba con fabricación, costos, publicación, venta, envío y cobro. No se crea todavía ese producto ni otro registro de seguimiento.

Auditoría de reutilización:
- La ficha productiva ya compone insumos/merma, operaciones de mano de obra, máquinas y costos fijos en services/composicion_costo_producto.py. Se conservan versiones históricas y orden/partes/lotes preparatorios.
- services/produccion_nucleo.py mantiene ejecución e impacto de inventario deshabilitados. El costeo del resultado productivo es una absorción teórica del plan/avance, no evidencia de consumos reales.
- El cálculo inverso ya existe en services/motor_comercial_canal.py y evalúa tramos de cargo fijo/umbral de envío. Se corrige ese motor; no se añade otro.
- Simulador comercial, preparación de publicaciones/observaciones, conciliación y lectores ML/MP permanecen en sus módulos actuales. Los ejemplos no acreditan que todo el circuito esté conectado.

Bloque de precio mínimo neto, base d25055fafa7c2b33870e144249b1005e62e25f0a:
- Hallazgo corregido: calcular la inversa continua y verificar una sola vez puede omitir un precio inferior válido o descartar un tramo por el redondeo independiente de las deducciones.
- Dentro de cada tramo/umbral se acota el error de los cargos porcentuales redondeados por separado. Se evalúan en orden los precios admisibles de la franja acotada con liquidar_precio existente; se toma el primero que alcanza el mínimo. No se supone monotonicidad del neto entre centavos.
- Si una política extrema exigiría más de 100000 evaluaciones para verificar la búsqueda, se rechaza para revisión. No se devuelve como mínimo comprobado una aproximación no verificada.
- Se conserva la firma y estructura de retorno del motor compartido. No se modifican reglas almacenadas ni fuentes de cargos.
- En el simulador existente se agrega Mínimo neto a percibir en este ensayo, paso de precio, publicidad, financiación del vendedor y previsión de devoluciones. El mínimo explícito manda sobre los porcentajes ilustrativos y debe cubrir al menos el costo declarado; no se le vuelven a sumar utilidad/impuestos.
- Sin mínimo explícito se conserva el ejemplo anterior, identificado como regla ilustrativa. No se usa ese recargo como sustituto de la regla insalvable.
- Se muestra neto al precio mínimo, excedente y desglose plegado de cada cargo. Importes de resultados con formato ARS existente, CSS acotado al simulador y sin cambios de navegación.
- Referencia comprobada: costo $4.000; mínimo $5.000; comisión 15%, publicidad 3%, financiación 2%, previsión de devoluciones 1%; cargo fijo $100 bajo umbral $10.000; envío $1.000 sobre umbral; paso $0,01. Precio mínimo $6.455,69, neto exactamente $5.000 y excedente cero. Son datos de ensayo, no tarifas actuales de ML.
- Precio de lista con descuento continúa siendo una referencia; cofinanciación, promociones/tramos por cantidad y vigencia real requieren su validación específica. No se declara lista real publicable ni garantía de liquidación futura.
- El monto del simulador no modifica ni consulta por sí mismo el mínimo configurado de un producto. El motor compartido recibe el piso resuelto por sus llamadores; completar y evidenciar el enlace de producto/costo/regla/canal es requisito antes del producto integral.
- Las alertas futuras deben respetar primero el mínimo neto; métricas de margen porcentual son complementarias y no pueden sustituirlo.

Verificación:
- 219 pruebas focalizadas aprobadas: 183 de rentabilidad/archivos ML/MP y 36 de motor/simulador/reglas/cargos/ruta. Incluyen comparación contra búsqueda exhaustiva independiente en 90 combinaciones de tasas, pisos, pasos y saltos; caso de redondeos separados; tasa extrema rechazada; mínimo explícito, rechazo bajo costo y formato monetario.
- Se ejecuta por AST la función real de la ruta del simulador y el conversor monetario, con contexto de prueba y plantilla real/layout mínimo. No se inicia la aplicación completa ni se verifica autorización/CSRF de esa ruta mediante este fixture; se conservan sus decoradores y protección existentes.
- Compilación Python aprobada. Sin navegador real, DB de staging ni prueba con canales. Visual del formulario ampliado pendiente de revisión agrupada.
- Sin cambios de modelos, migraciones, app.py, bootstrap, scheduler, webhooks, estados operativos, credenciales, flags o producción. No se cargan productos ni se activan conexiones.

Dependencias que siguen abiertas antes de iniciar el caso integral:
| Bloque | Qué falta completar o evidenciar | Condición para avanzar |
| --- | --- | --- |
| Fabricación + inventario + calidad | Aplicar elegibilidad por calidad a propuestas; no contar lotes rechazados/cuarentena como disponibles; comprobar materiales suficientes y resolver cantidades fraccionarias/unidades. | No habilitar ingreso/consumo por un informe de consistencia si falta stock, conversión o calidad. |
| Costos + mínimo neto + publicación | Encadenar/evidenciar la ficha y su versión con la regla económica aplicable, mínimo neto y política de canal/vigencia/cobertura, incluido embalaje una sola vez. | Precio verificado con cargos vigentes y explicación de cada componente; faltantes bloquean aprobación como cumplido. |
| Venta + envío + cobro | Vincular el mismo SKU/publicación/variante y cantidades, costo congelado, envío compartido y cobros/cargos únicos. Completar estados/ajustes pendientes según alcance del caso. | Recorrido coherente de punta a punta en laboratorio; sin órdenes externas ni dinero real. |
| Operación conectada posterior | Permisos/cobertura de cuentas reales, reportes MP, promociones/B2B, acciones de publicación y logística externa. | Etapa separada; no se activa para satisfacer el ensayo desconectado. |

Siguiente trabajo: resolver Fabricación + inventario + calidad como bloque, conservando UAT-OP-001 y sus antecedentes sin usarlos como permiso para ejecutarla. No se pide al usuario cargar un producto nuevo ni repetir las siete pruebas de rentabilidad. Las dos variantes MP del commit anterior siguen pendientes de UAT de interfaz y pueden revisarse junto con el siguiente despliegue; no bloquean el desarrollo por pedir otra ronda aislada.


### Bloque conjunto: fabricación, materiales y elegibilidad por calidad — 19/10/2026

El usuario confirmó deploy listo después de 01c49c28180dadd1b1602929226b2dafd313a6ac. Se registra la confirmación sin atribuirle una prueba funcional ni una verificación independiente del SHA desplegado.

Base: 01c49c28180dadd1b1602929226b2dafd313a6ac. Desarrollo exclusivo de integración, sin cargar un producto nuevo ni modificar UAT-OP-001.

Correcciones:
- Propuesta Producción–Inventario: el ingreso teórico deja de tomar todas las unidades buenas de los partes. Reutiliza lotes/controles existentes y suma únicamente lotes aprobados internamente cuyo último control coherente corresponda al mismo lote/orden/parte/organización/unidad.
- Cuarentena, en control, rechazo, falta de control, parte anulado/ajeno, controles contradictorios, impactos previos y sobreasignación del parte bloquean la aprobación de la propuesta. Las unidades sin lote se exponen; no pasan automáticamente como aprobadas.
- El control por muestra conserva la semántica existente de aprobación interna del lote; no se afirma inspección del 100% de las unidades ni certificación externa. La cantidad elegible sigue sin ser stock liberado.
- Con lotes mixtos puede verse un ingreso teórico solo por la cantidad elegible, pero la propuesta queda observada por las unidades retenidas/rechazadas. Los consumos teóricos conservan todo el avance informado, incluido rechazo: no se reducen para ocultar pérdidas.
- Los consumos evalúan stock neto luego de reservas y bloqueos. Cantidades faltantes, no finitas, negativas o desconocidas bloquean; no se reemplazan por cero. Varios insumos no reutilizan virtualmente el mismo saldo de una existencia.
- El destino único también se valida con la guardia existente de SKU principal, ubicación, producto, organización y control activos.
- Plan agregado: se distinguen consistente, disponibilidad_suficiente y compatible_con_inventario. Tener mapeos consistentes no aprueba un plan con faltantes. Sin demanda pendiente no acredita disponibilidad para los consumos del avance ya informado.
- Las fracciones se conservan como Decimal, hasta seis decimales, sin convertirlas a enteros. Como el inventario operativo sigue almacenando enteros, el plan/propuesta con cantidades fraccionarias queda incompatible/no aprobado para ese alcance. No se implementa una conversión implícita ni se trunca/redondea para hacerlo pasar.
- Expediente consolidado: utiliza los resultados corregidos y agrega la disponibilidad compartida de los consumos de todas las órdenes, para no presentar como apto un conjunto que use dos veces el mismo stock.
- Se conserva el estado no ejecutable: cero movimientos, reservas, compras, cierres o liberaciones reales; sin cambio de versiones de costo.

Presentación:
- En /admin/produccion se agrega Disponibilidad de materiales y calidad, plegado, con faltantes de demanda pendiente y buenas/elegibles/no elegibles/sin lote por orden aprobada.
- Se aclara que la propuesta comprueba por separado los consumos del avance. Los informes existentes siguen accesibles y mantienen sus rutas; no se duplica un expediente ni una pantalla.
- Se normaliza el texto Stock: bloqueado. Se reutiliza CSS existente, tablas contenidas, sidebar y formularios.

Verificación: 66 pruebas focalizadas aprobadas y compilación Python aprobada.
- Incluye los servicios reales de materiales, calidad, propuesta, capacidad, costeo y expediente; casos de control más reciente contradictorio/ajeno, cuarentena/rechazo, sin lote, sobreasignación, reservas/bloqueos, faltantes de stock, fracción exacta 2,1 y stock desconocido.
- Caso de dos órdenes con consumo 16 cada una y disponibilidad compartida 20: faltante acumulado 12, expediente no apto; no se modifica el saldo.
- Caso de fracción 2,1 con stock 3: consistente y disponibilidad suficiente, pero incompatible con inventario entero/no aprobado. Con stock 2: faltante exacto 0,1, sin truncamiento.
- Render Jinja de plantilla real con layout mínimo comprueba sección plegada y avisos; no es inspección visual en navegador. Las pruebas existentes usan objetos de dominio de prueba, sin Postgres ni cuenta conectada.
- No se inicia la aplicación completa ni se prueba el ORM de staging. Se conservan filtros de sesión/rol/contexto existentes; no se cambian esquema, migraciones, app.py, scheduler, webhooks, flags, credenciales ni producción.

Límites y trabajo que continúa:
1. Sigue pendiente resolver la representación/unidades de cantidades fraccionarias en todo el inventario (existencias, reservas, movimientos y consumidores). El control nuevo bloquea esa incompatibilidad; no la declara implementada. Evaluar una solución coherente y migración aislada antes de habilitar consumos.
2. La disponibilidad es una fotografía de lectura y asignación virtual, no una reserva transaccional ni prueba de consumos físicos. La ejecución sigue deshabilitada aun con un expediente apto para ensayo.
3. Costeo de avance conserva absorción teórica del plan, no costeo de consumos reales. Conexión producto/costo/regla/canal y futuros ajustes de ML/MP siguen pendientes como se indicó en el bloque anterior.
4. Se conservan las pruebas y pendientes visuales históricos. No se declara todo Producción terminado ni habilitado el caso integral.

UAT agrupado cuando se despliegue este bloque:
- Producción → Planificación productiva → Disponibilidad de materiales y calidad. Revisar órdenes existentes; no crear ni ejecutar otra.
- Captura de la sección y descarga de la Propuesta Producción–Inventario de UAT-OP-001 / expediente actualizado para comprobar calidad, consumos y bloqueos del mismo circuito. El informe nuevo puede cambiar su aptitud respecto al histórico porque ahora verifica faltantes y calidad que antes no incidían.
- No ingresar stock, aprobar lotes rechazados ni modificar cantidades solo para obtener un indicador verde. No repetir las altas previas ni las siete pruebas de rentabilidad.


### UAT recibido: cruce de materiales y calidad — 19/10/2026

Evidencia aportada después del despliegue informado de 4d9a65ed2cd606fd72d6456fa652ab16e021ae99:
- Captura image(20261019-155458).png: sección Disponibilidad de materiales y calidad; UAT-OP-001 con 9 buenas, 6 elegibles, 3 no elegibles y 0 sin lote. Sin demanda pendiente aclara que no acredita materiales para consumos ya informados.
- Archivo propuesta_inventario_produccion_1 (2).json: huella canónica verificada feb634f795a67e125ff3fc3347712416fb65860447b2e408bc76902ea11adefc; simulación 7a1bc06ca4a6cf336d41beb615d5bbd99575e9a5c2cc9c9695cb0a26beb4caeb.
- Organización 1/unidad 3/orden 1: salida teórica 21, disponibilidad 0 y faltante 21; ingreso teórico 6, excluyendo las 3 rechazadas. Hallazgos lote_rechazado y material_insuficiente; aprobada=false/habilita_ejecucion=false.
- Se acepta este cruce limitado de calidad y materiales. No implica liberación, consumo físico, conexión externa ni habilitación integral. No se corrige stock ni se aprueba un lote rechazado para obtener un indicador verde.

### Bloque conjunto: unidades fraccionarias de materias primas — 19/10/2026

Base oficial: 4d9a65ed2cd606fd72d6456fa652ab16e021ae99. Se reutilizan ItemInventario.atributos_json, maestro de SKU y servicios de propuestas; sin tablas, migraciones ni inventario paralelo.

Implementado:
- Compras → Mapeo de insumos a inventario → Preparar materia prima permite definir la precisión de un SKU NUEVO: unidad, milésima o millonésima de la unidad del insumo. Ejemplo: insumo/costeo en kg, SKU en g con factor 1000. Para otras unidades se declara una fracción de la misma unidad; no se supone equivalencia de peso/superficie/volumen.
- La equivalencia queda persistida al preparar la identidad inactiva y sin stock. Repetir igual es idempotente; intentar cambiar unidad/precisión de una identidad existente se rechaza. Las identidades anteriores mantienen factor 1; no se reinterpretan saldos, reservas ni historial.
- Un conversor exacto compartido valida identidad del insumo/SKU/producto, organización/unidad, origen declarado, precisión y límite Integer. Las cantidades que no se representan en enteros de la unidad base no se redondean ni se habilitan. Se mantiene la precisión de seis decimales de las cantidades fuente del circuito existente.
- Plan de materiales compara demanda convertida con existencias/reservas/bloqueos en unidad base. Demanda, asignación y sugerencia de compra permanecen expresadas también en la unidad fuente del insumo. Las fracciones representables ya no son un bloqueo por sí mismas; stock/calidad siguen siendo requisitos separados.
- Propuesta de producción identifica cantidad fuente, factor y cantidad base; el producto terminado sigue contando unidades enteras. Expediente y disponibilidad compartida utilizan la cantidad base. Propuestas/reversiones siguen siendo teóricas y no ejecutables.
- Propuestas de compras, tanto iniciales como habilitadas después del mapeo, usan la misma conversión. Unidad de compra diferente/ausente, cantidad no representable y mapeos ambiguos o ajenos mantienen bloqueo con motivo. No se reabren decisiones finales ni se reescriben propuestas históricas ya preparadas/aprobadas.
- Precio unitario y obligación de compra conservan su base/importe original: 2,1 kg a 10.000 centavos/kg son 21.000 centavos, mientras el stock propuesto sería 2.100 g.
- Inventario conserva sus campos y operaciones enteras existentes. La unidad se muestra junto al SKU, destinos, movimientos, reservas, transferencias y conteos. El Excel de conteo agrega UNIDAD; se verifica al importar materias primas. Plantillas anteriores siguen admitidas para unidades sin escala; un SKU fraccionario requiere plantilla con unidad explícita.
- Compras muestra la equivalencia junto a la propuesta y el motivo concreto del bloqueo. Se reutilizan modal, clases y sidebar actuales; no se agrega otra pantalla.

Verificación:
- 133 pruebas focalizadas aprobadas del conjunto local de producción, calidad, materiales, propuestas, capacidad, costeo, expediente, materias primas, compras y conteos. Incluyen 33 casos del conversor/cruce/presentación, persistencia SQLite de identidad e inmutabilidad, cantidades mínimas, exceso de precisión/desborde, unidades/tenant cruzados, compra nueva y mapeo posterior, importación Excel sin escritura ante unidad errónea y regresiones de calidad/stock compartido.
- Ejemplo comprobado: 2,1 kg → 2.100 g; con 2.500 g brutos, reserva 300 y bloqueo 200, faltan 0,1 kg; con 2.600 g la demanda es suficiente. No se mutan existencias durante planificación.
- Compilación Python aprobada. Render Jinja de plantillas reales con layout mínimo; no equivale a inspección visual en navegador. No se ejecuta la suite completa del repositorio ni se inicia la aplicación, Postgres o una sesión de staging. Persistencia probada con modelos reducidos SQLite; no es ensayo de migración.
- Sin cambios a modelos, app.py, bootstrap, scheduler, webhooks, credenciales, flags o producción. No se ejecutan movimientos, publicación, reservas reales ni dinero durante estas pruebas.

Alcance pendiente y siguiente trabajo:
1. La representación fraccionaria queda disponible para SKU nuevos preparados con escala explícita. La migración de SKU existentes con saldos/historial, cambios de unidad de insumos y revisión de propuestas antiguas sin unidad siguen pendientes de un procedimiento específico; este bloque no los convierte.
2. No se habilita ejecución de fabricación por disponer de unidad compatible. Materiales/calidad/capacidad/costos y transacciones siguen requiriendo sus controles; la disponibilidad continúa siendo una fotografía.
3. Continúa el enlace producto/ficha/versión de costo → regla/mínimo neto → cobertura/canal/publicación, sin duplicar el motor ya implementado. Costeo por consumos físicos reales y operación conectada continúan pendientes.
4. No se solicita aún cargar el producto integral. UAT agrupado al desplegar: abrir Compras → sección 5 Mapeo de insumos a inventario → Preparar materia prima y comprobar selector de precisión; cerrar sin guardar. Revisar unidades en las existencias actuales sin modificar saldos. Para validar conversión de un SKU nuevo se preparará un caso separado cuando corresponda; no reutilizar UAT-OP-001 para ejecutar nada.
5. Se conservan los pendientes visuales históricos y las dos variantes negativas MP pendientes de interfaz. No se declara terminado todo el sistema.


### Enlace verificable de costo, piso económico y precio de canal — 19/10/2026

Base oficial: 751ebdb411fd0c955feb6a6cd66d881f36deb9f8, rama integracion-saas-2026-09. El usuario respondió LISTO al bloque anterior; se registra esa confirmación sin atribuirle una captura, prueba de conversión nueva ni verificación independiente del deploy.

Auditoría y reutilización:
- Comercial ya invocaba resolver_regla_vigente/calcular_pisos_regla y calcular_precio_minimo_canal. Se conserva esa implementación; no se agrega otro motor de margen/precio ni otro módulo de publicaciones.
- El armado anterior elegía la primera inclusión del producto y cruzaba las políticas vigentes sin comprobar composición, moneda, vigencia temporal ni cobertura completa de tramos. Una excepción de una fila también podía interrumpir toda la consulta.
- Se extrae ese armado a services/enlace_economico_producto.py y se integra en la consulta y bandeja existentes. Solo lee fuentes de la organización/unidad actuales. Las inclusiones inactivas no compiten; varias inclusiones activas requieren una asociación inequívoca futura y se bloquean, sin escoger la primera.

Comportamiento:
- Requiere una versión de costo vigente, en ARS, con perfil activo/único del mismo producto/contexto. Recalcula sus subtotales con el servicio existente para comprobar el total; para producción/combo compara la composición actual con el snapshot aprobado reutilizando construir_detalles/construir_detalles_combo y huella_detalles.
- Conserva la prioridad económica producto → catálogo → unidad → organización. Excepciones ambiguas, referencias inconsistentes, estados/fechas incompatibles y fuentes ajenas bloquean esa fila. No se sustituye una excepción inválida por una regla general menos exigente.
- La política de canal debe pertenecer a una lista de la misma organización/unidad/moneda, ser única y estar vigente. Los cargos deben cubrir desde cero hasta un tramo final sin límite, sin huecos ni solapamientos. Cargo cero se declara como tramo explícito; ausencia de tramo/porcentaje no se trata como cero.
- El motor compartido obtiene el mínimo y objetivo por separado. El precio mínimo conserva la regla irrevocable: menor precio admisible cuyo neto calculado cubre el mínimo a percibir, con reevaluación de tasas, cargos, envío y redondeos.
- Los fallos se muestran como Cálculos pendientes de revisión, dentro de Políticas comerciales, sin producir precios para esas combinaciones ni impedir calcular otras filas válidas.
- Cada cálculo conserva perfil, producto/SKU, catálogo/inclusión, versión/composición de costo, regla económica, política/tramos, importes y fechas. La huella del enlace incorpora esos datos y el resultado, con fechas normalizadas a UTC.
- La cola interna incluye esa huella al preparar nuevas propuestas. Cambiar la versión económica/política/composición invalida la propuesta anterior aun si el precio numérico queda igual. Los snapshots históricos no se reescriben ni se reabren decisiones; su revisión puede indicar obsolescencia al compararlos con el cálculo actual.
- La exportación existente de Control comercial agrega IDs de origen, huella y alcance. Se mantienen columnas anteriores y sus posiciones.

Presentación:
- Costos y precios → 5. Políticas comerciales → Simulación sin publicar: tabla compacta de seis columnas con mínimo, neto/piso y objetivo separados.
- Gestionar abre el detalle en el diálogo y con los controles existentes del catálogo: fuentes, deducciones calculadas, neto y excedente. Cerrar no envía modificaciones ni requiere escribir una confirmación.
- Se reutilizan sidebar, CSS y JS actuales. No se crea otra pantalla ni se cambia navegación.
- La bandeja deja de describir su cálculo como precio seguro sin matices: muestra su alcance como cálculo según versiones internas.

Verificación:
- 97 pruebas focalizadas aprobadas; 42 casos del nuevo enlace y sus cruces/presentación. Incluyen búsqueda exhaustiva del primer precio admisible del ejemplo, salto de envío/cargo, costo 2,1 kg sin multiplicarlo dos veces, total/subtotal incoherentes, versiones y catálogos ambiguos, unidad/tenant/moneda, vigencias UTC, cobertura de tramos, producción/combo desactualizados, exportación y obsolescencia con igual precio.
- Se ejecuta la función real de consulta del panel extraída por AST con dobles de ORM, conservando el nuevo enlace real y la bandeja real. Verifica que perfiles se consulten con organización/unidad y que errores se expongan sin simulación. No es una prueba del ORM PostgreSQL ni de autorización HTTP.
- Render Jinja del panel y popup reales con layout mínimo; verifica IDs y controles existentes de apertura/cierre. Sin inspección visual en navegador ni sesión real de staging. Compilación Python aprobada.
- Regresiones focalizadas del motor, reglas, publicidad/cuotas, simulador, bandeja, cola y validación de canal aprobadas. No se ejecuta la suite completa del repositorio ni se inicia la aplicación/scheduler.
- Sin cambios a app.py, modelos, migraciones, bootstrap, scheduler, webhooks, estados operativos, credenciales, flags o producción. No se publican precios, se reservan materiales ni se ejecutan movimientos/cobros.

Límites pendientes antes del producto integral:
1. El enlace nuevo acredita coherencia de las versiones internas, no una consulta real ML/MP. La traza marca cargos_contrastados_cuenta=false y habilita_publicacion=false. Publicidad, financiación, devoluciones y envío son parámetros/previsiones de esa política.
2. Embalaje no se infiere por el nombre de un insumo o su ficha física. Se marca embalaje_verificado=false y se pide verificar su inclusión en la composición; no se suma otro cargo automáticamente. Falta registrar y reutilizar esa evidencia explícita para cerrar el mínimo completo sin doble conteo.
3. Falta enlazar esta traza con la cuenta/publicación/variante exactas, observaciones vigentes y cobertura real de cargos/promociones, y con el snapshot de la venta offline. No se declara el módulo ML terminado ni rentabilidad real asegurada.
4. Se mantienen el motor histórico de listas y su plan de transición, la falta de ejecución productiva y el costeo físico real pendiente. El nuevo control no migra esos consumidores ni activa conexiones.
5. Los casos antes tolerados pueden aparecer ahora bloqueados. Revisarlos por su motivo; no inventar datos o cargar stock para obtener verde. Las versiones vigentes con cobertura incompleta requieren una nueva política preparatoria explícita, sin modificar la historia.
6. La validación de fichas lee fuentes actuales; no se ha medido rendimiento masivo en staging ni concurrencia transaccional. Los resultados siguen siendo fotografías de solo lectura.

UAT agrupado tras desplegar:
- Abrir /admin/comercial#politicas (Costos y precios → 5. Políticas comerciales).
- Si hay una combinación completa, Gestionar debe abrir el detalle de versiones y neto/piso, con embalaje/cuenta pendientes explícitos. Cerrar y volver a abrir conserva los datos.
- Si las fuentes actuales no cumplen, revisar Cálculos pendientes de revisión: debe identificar producto/lista y motivo sin error 500. No hace falta cargar un producto nuevo para esa inspección.
- Siguen pendientes las variantes negativas MP de interfaz y demás pendientes históricos. No repetir las altas previas ni cargar todavía el producto integral.


## 2026-10-19 — Embalaje declarado, identidad de publicación y contraste parcial

Continuidad UAT previa:
- Capturas 170013 a 170323: UAT-PROD-001 estaba en borrador/no disponible; activar la inclusión interna conservando No disponible resolvió el bloqueo de catálogo. Luego el cálculo identificó la cobertura de cargos faltante, sin inventar cero.
- Capturas 170757/170818 eran estados intermedios: no acreditaban cobertura completa.
- Captura 170933: UAT-POLITICA-002 v2 de Lista de prueba UAT, comisión 10 %, resto de porcentajes y envío explícitos en cero, paso $1 y tramo desde cero hasta sin límite con cargo cero. UAT-POLITICA-001 v1 quedó archivada.
- UAT-PROD-001: perfil/catalogo/inclusión 1, costo v2 $4.933,65, regla UAT-REGLA-001 v1 unidad:3, mínimo neto $5.921, precio mínimo $6.579, comisión $657,90, neto $5.921,10 y excedente $0,10. Captura 171103 conserva esos importes en la tabla, objetivo $7.127 y confirma cierre visual. No acredita una reapertura ni persistencia independiente.
- La captura mostró el pie Cerrar superpuesto al contenido durante el desplazamiento. El nuevo CSS limita el ajuste a este diálogo y ubica el pie después de todo el contenido.

Bloque implementado:
- Reutiliza el enlace económico, motor, simulación, bandeja, observaciones de canal y popup existentes. No crea otro catálogo, libro de cargos, cuenta conectada ni esquema de base.
- Nueva evidencia local versionada dentro del campo existente CatalogoProducto.canales_json, clave reservada _coberturas_economicas. Conserva los metadatos ML/TN; editar normalmente el catálogo conserva la evidencia. Ambas escrituras bloquean la inclusión para serializar versiones. Máximo 100 versiones; alcanzar el límite rechaza otra carga sin borrar historia.
- Registra organización/unidad, inclusión/lista, versión de costo y huella de fuentes, cuenta/publicación/variante declaradas, modo y referencia del embalaje, autor/fecha y huella de evidencia.
- Modos: incluido (selección explícita de líneas del costo vigente, sin sumarlas otra vez), adicional por unidad vendida (se cubre antes de comparar el neto con el piso económico original) o sin costo declarado con referencia. Ausencia de evidencia nunca equivale a cero.
- Un adicional de $100 en el ejemplo UAT, con fuentes sin cambios, requiere $6.690, comisión $669 y neto después del embalaje $5.921. El costo aprobado $4.933,65 y el piso original $5.921 permanecen intactos. No se vuelve a aplicar margen sobre ese adicional.
- Cambiar costo/composición/regla/política vuelve obsoleta la evidencia anterior: queda visible para revisión pero no se aplica. Se rechazan huellas antiguas, líneas ajenas/duplicadas, contextos ajenos y modos contradictorios. Un reintento idéntico no agrega versión.
- Las propuestas internas nuevas se bloquean mientras la cobertura sea pendiente o requiera revisión. La huella ampliada invalida propuestas anteriores si cambia la evidencia o su contraste.
- El contraste usa únicamente observaciones ya existentes de precio, comisión/cargo y envío para organización/unidad/lista/inclusión/cuenta/publicación exactas, con regla de vigencia única y activa. Faltantes, futuras/vencidas, contradicciones o diferencias quedan pendientes. Una variante declarada sigue pendiente porque esas observaciones no identifican variantes.
- Coincidir solo acredita comisión/cargo/envío al precio observado. No acredita identidad OAuth, todos los tramos de precio, impuestos, promociones, publicidad, financiación o liquidaciones reales. cargos_contrastados_cuenta y habilita_publicacion continúan false. embalaje_verificado indica coherencia de la declaración interna con las fuentes, no comprobación externa.
- Control comercial descuenta el adicional una sola vez, tanto para precio observado como propuesto. Además deja de conservar automáticamente un precio observado más alto: exige que su neto cubra el objetivo, porque un salto de envío/cargo puede volverlo insuficiente. En ese caso propone internamente el precio recalculado admisible, incluso si es menor, sin ejecutarlo.

Presentación:
- Misma ruta Costos y precios → 5. Políticas comerciales → Simulación sin publicar → Gestionar.
- Formulario compacto de dos columnas, líneas de costo plegadas, estado y motivos de contraste legibles, pie al final. Guardar evidencia y recalcular pide confirmación con botones, sin texto escrito.
- Cerrar, X o Escape descartan cambios locales al cerrar. Enter en campos no envía el formulario. El selector habilita solamente el importe o las líneas aplicables para evitar envíos contradictorios.
- Se mantiene la navegación/sidebar; no se crean pantallas ni accesos nuevos.

Verificación:
- 141 pruebas focalizadas aprobadas: 97 anteriores y 44 nuevas de cobertura, persistencia/guardas y formulario.
- Persistencia de JSON en tabla reducida SQLite, lectura posterior y conservación de historia al editar metadatos; no equivale a probar PostgreSQL ni concurrencia real.
- Ruta real extraída por AST y ejecutada por HTTP de Flask con dobles de acceso/ORM: escritura válida con bloqueo, rechazo de unidad/tenant/huella/línea ajena. No prueba middleware real de autenticación/CSRF; la ruta conserva login_required y el formulario token CSRF.
- Node VM verifica selector, Enter, confirmar/cancelar y reset tras cierre; no es inspección visual de navegador.
- Incluye ejemplo monetario UAT exacto, no duplicación de embalaje, idempotencia, obsolescencia, contraste exacto/parcial y salto de envío con precio mayor insuficiente. Compilación Python y sintaxis JavaScript aprobadas.
- Sin suite completa ni arranque de aplicación/scheduler. Sin cambios a app.py, modelos, migraciones, bootstrap, flags, webhooks, estados, credenciales o producción. Sin nuevas conexiones externas, publicaciones, reservas, stock, dinero o cobros.

UAT agrupado pendiente tras desplegar este bloque:
1. En la ruta indicada, Gestionar sobre UAT-PROD-001 / Lista de prueba UAT.
2. Declarar cuenta CUENTA-UAT, publicación PUB-UAT-PROD-001, variante vacía, Gasto adicional por unidad vendida, $100 y referencia UAT-EMB-001. Son referencias ficticias locales.
3. Guardar y confirmar. Con las fuentes documentadas sin cambios: precio mínimo $6.690 y neto $5.921 después del embalaje. Recargar y reabrir debe conservar evidencia e importes.
4. Cambiar localmente importe a $200 y cerrar; reabrir debe mostrar $100. Cancelar la confirmación de guardado también debe conservar la versión anterior. Verificar pie y campos sin superposición.
5. Los faltantes de observación/cuenta son esperables: no cargar datos inventados para obtener coincidencia ni conectar cuentas.

Pendientes conservados:
- La última evidencia por inclusión/lista es la que aplica; versiones anteriores se conservan. No resuelve políticas simultáneas para varias cuentas/variantes de la misma inclusión/lista.
- Identidad real, cobertura completa de deducciones/promociones, venta offline y snapshot de costos/cargos/embalaje de esa venta, conciliación ML/MP y demás etapas del plan siguen pendientes. No declarar rentabilidad real asegurada.
- Pendientes históricos de interfaz/negativos MP y prueba física integral siguen abiertos. No cargar todavía un producto integral nuevo; continuar sobre el ejemplo UAT existente.


## 2026-10-19 — Del cálculo guardado a la venta de prueba y su comparación

UAT anterior confirmado:
- Captura image(20261019-173153).png inspeccionada localmente: UAT-PROD-001 muestra precio mínimo $6.690, neto/piso $5.921 y objetivo $7.238 después del embalaje adicional de $100.
- Tras pedir refrescar/reabrir y cambiar a $200 cerrando sin guardar, Martín respondió perfecto. Se registra como confirmación del usuario de persistencia y descarte local; no como inspección automatizada de su sesión.
- El bloque de embalaje quedó desplegado por el usuario; no se ejecuta un despliegue desde estas herramientas.

Auditoría y alcance:
- Ya existen rentabilidad_ml_offline.analizar_rentabilidad, conciliar_venta, escenarios sintéticos, lectura de archivos ML/MP, exportación/relectura y la pantalla de rentabilidad con sidebar. Se reutilizan.
- Este bloque enlaza la simulación económica de un producto con ese analizador. No crea otro motor de rentabilidad ni otro libro financiero.
- Solo una unidad y operación sintética. No representa la venta real, una liquidación/cobro MP, el circuito operativo de pedidos ni un precio mayorista. El caso integral físico y la conciliación de datos reales siguen pendientes.

Implementación:
- Gestionar, con evidencia de embalaje declarada vigente, ofrece Preparar venta de prueba. Usa exclusivamente lo ya guardado; el texto aclara que los cambios sin guardar no se trasladan.
- Ruta GET de lectura con login/admin/contexto existentes, unidad explícita, inclusión/lista inequívocas y huella del cálculo actual. Cambios de fuentes, identificadores ajenos o evidencia obsoleta redirigen con motivo, sin preparar otra combinación por aproximación.
- La ruta reconstruye el cálculo con la consulta actual y congela costo/version/composición, regla económica, política/tramos, embalaje, cuenta/publicación/variante declaradas y fecha UTC. Sin escritura en DB ni cambios a app.py.
- Dos casos: gastos según lo previsto y envío $500 más caro. El segundo modifica hechos sintéticos y su cobro, manteniendo la previsión: no recalcula el esperado para borrar la diferencia.
- La cuenta técnica continúa demo-rentabilidad-sin-conexion; la cuenta/publicación declaradas se conservan en las fuentes. No se amplía la importación para aceptar cuentas reales.
- El previsto del analizador es la liquidación de canal ANTES del embalaje local. El gasto local previsto se descuenta una sola vez. La comparación con el mínimo usa el neto económico DESPUÉS de gastos/embalaje, no confunde saldo cobrado con resultado económico.
- Ejemplo actual: precio $6.690, costo $4.933,65, liquidación de canal $6.021, embalaje $100, mínimo/neto $5.921; resultado económico previsto y de ensayo $987,35. Con envío extra $500: neto económico $5.421, resultado $487,35 y diferencia -$500 respecto del previsto y del mínimo.
- Aviso bajo mínimo dentro del resultado, con los componentes comparados. No hay nuevas notificaciones persistentes ni scheduler. El caso base solo cubre los conceptos simulados; impuestos y fuentes externas siguen pendientes. No se presenta como margen asegurado ni alerta definitiva.
- No se multiplican envíos/cargos de un pack, no se infieren descuentos mayoristas, no se confunde una previsión de devoluciones con evidencia real: todos los hechos del nuevo ensayo están rotulados como sintéticos.

Archivo e integridad:
- La exportación existente incluye entrada, resultado y fotografía del cálculo. Al releer, se ignora el resultado exportado y se recalcula con el analizador existente.
- La fotografía conserva sus fuentes históricas y no consulta costos actuales al releer. No se aplica el costo actual a una venta anterior a la fecha del snapshot. Las fuentes debían estar vigentes cuando se congelaron y el costo debe corresponder a la fecha de la operación.
- Se comprueban huella del snapshot y del enlace, contexto, SKU/publicación/variante, cantidad única, versión/importe/fechas de costo, modo de embalaje, previsión de canal y gastos locales. Se vuelve a usar el motor y regla económica compartidos para reproducir el primer precio admisible y su piso.
- Tasas ausentes no se convierten en cero. Reutiliza la validación de cobertura de cargos y limita el ensayo a 1..200 tramos. La huella detecta cambios y comprueba coherencia, no es firma de autenticidad ni certifica origen externo.
- El enlace solo admite origen sintético. No habilita importar ventas reales bajo una previsión rehecha. Archivos antiguos sin enlace conservan su contrato y sus validaciones previas.

Presentación:
- Reutiliza la pantalla Rentabilidad por venta y publicación, componentes y diálogos existentes. Caso selector arriba, resultado con mínimo/neto previsto/neto del ensayo/diferencia y fuentes plegadas.
- Elegir otros ejemplos se pliega cuando ya existe resultado; las fuentes extensas se mantienen plegadas. Descarga usa el botón/JS ya existentes. Volver al cálculo retorna a Políticas.
- No hay nuevos diálogos de confirmación escrita, accesos laterales, formularios operativos ni persistencia del ensayo en sesión.

Verificación:
- 281 pruebas focalizadas aprobadas: las 141 del bloque previo, 97 regresiones existentes del analizador/archivo/rutas offline incorporadas a la ejecución, y 43 casos nuevos del puente.
- Nuevas pruebas: importes UAT exactos, envío extra y alarma, embalaje incluido/sin costo sin doble descuento, exportación/relectura conservando fuentes al cambiar el costo actual, resultado exportado ignorado, contexto/fecha/versión/identidad/previsión incoherentes rechazados, huellas rehechas con cálculo no reproducible rechazadas, ausencia de tasas/tramos y embalaje contradictorio, vigencia de evidencia y límite del caso de envío.
- Ruta real extraída por AST y ejecutada por HTTP Flask con dobles de acceso/ORM; renderiza la plantilla real y extrae el JSON para reanalizarlo. Comprueba rechazo de acceso/contexto, no-store, enlaces, selector, descarga, avisos y popup sin formularios anidados. El decorador login_required se verifica en el AST; no equivale a prueba del middleware ni del ORM PostgreSQL.
- Regresiones de archivo y rentabilidad sintética, multiórdenes, cargos, retenciones, devolución, costos históricos y rutas autorizadas siguen aprobadas. Compilación Python aprobada.
- No se inicia app/scheduler ni se ejecuta la suite completa. Sin prueba visual de navegador real. Pendiente UAT en staging.
- Sin modelos/migraciones/bootstrap, flags, credenciales, webhooks, publicación externa, conexiones nuevas, reservas, stock, pagos ni producción.

UAT agrupado tras desplegar:
1. Costos y precios → 5. Políticas comerciales → Simulación sin publicar → Gestionar de UAT-PROD-001 → Preparar venta de prueba, con embalaje $100 ya guardado.
2. Caso Gastos según lo previsto: mínimo/neto $5.921 y resultado $987,35 con fuentes actuales sin cambios. Se informa alcance parcial, no rentabilidad real certificada.
3. Caso Envío $500 más caro → Comparar venta de prueba: neto $5.421, diferencia -$500 y aviso bajo mínimo. La previsión debe permanecer $5.921.
4. Descargar ensayo con cálculo congelado, analizarlo en el formulario offline de esa misma pantalla y comprobar importes/alerta/fuentes conservados. No editar JSON ni descargar otros archivos para este caso.

Pendientes:
- Venta real/offline con su fecha y snapshot aprobado antes de vender, cobros y gastos efectivamente documentados, deducciones/promociones completas y conciliación de cuenta ML/MP. No se considera terminado el módulo ML ni la fabricación/envío físico integral.
- Varias unidades, packs con envío/cargos compartidos, variantes y precios por cantidad deben enlazarse sin extrapolar el caso de una unidad.
- Pendientes históricos, negativos MP de interfaz y estética no revalidados continúan abiertos. No cargar todavía el nuevo producto integral.


## 2026-10-19 — Previsión congelada vinculada a snapshots ML/MP

UAT confirmado del bloque anterior:
- Capturas 195555/195632: UAT-PROD-001, precio $6.690, costo $4.933,65, comisión $669, embalaje $100, neto $5.921 y resultado $987,35. Detalle visual legible en popup.
- Capturas 195851/195907: el embalaje guardado pasó a $500; el cálculo respondió con precio $7.135, comisión $713,50, neto $5.921,50 y excedente de $0,50. No era todavía el caso de envío mayor.
- Captura 200810: caso Envío $500 más caro, con precio $7.135 intacto y embalaje $500. Neto previsto $5.921,50; neto ensayo $5.421,50; faltante frente al mínimo $499,50; resultado $487,85 y diferencia -$500. Alerta roja correcta.
- Captura 201331: relectura offline del archivo conserva esos importes, fuentes y alerta. Queda validada por captura la descarga/relectura del ensayo, sin certificar datos externos.
- No repetir el bloque anterior ni volver a cambiar embalaje para probar gastos observados. La configuración actual de staging tiene embalaje $500; los ejemplos antiguos de $100 siguen documentados como historia.

Auditoría y reutilización:
- Los lectores offline ML/MP ya normalizan órdenes, publicaciones, envío del vendedor, pagos y grupos explícitos de cargos; el analizador evita duplicar los hechos coincidentes.
- La previsión congelada del producto no se trasladaba por datos_locales a la entrada normalizada ML. Se conserva ahora ese enlace explícito, sin consultar el costo vigente al releer.
- No se crea otra integración, conciliación, libro de movimientos, cotizador ni método de cálculo de margen. Se utilizan analizar_archivo, normalizar_snapshot_ml/mp y analizar_rentabilidad.

Bloque implementado:
- Desde la venta de prueba del producto: Contrastar el cobro ML + MP de este producto, plegado inicialmente.
- Tres casos: cobro/cargos coincidentes, MP sin neto informado y MP con $100 más de comisión. Usa el mismo producto y su previsión, no los ejemplos genéricos de otros SKU.
- Prepara el paquete en el contrato offline existente (orden/publicación/envío ML, costo/previsión/embalaje locales y pago/relaciones de cargos MP). La generación es ficticia y de una sola unidad; no llama APIs ni genera datos operativos.
- El propio paquete pasa por los lectores y el analizador existentes antes de presentarse. La descarga contiene el paquete original, no solo el resultado calculado, con nombre rentabilidad_producto_ml_mp_<caso>.json. Releer ignora el resultado exportado y vuelve a normalizar/recalcular.
- El lector ML conserva enlace_precio cuando se declara dentro de datos_locales. El verificador admite ahora, además del ensayo, ese enlace en archivos normalizados de snapshot ML declarado. Se mantiene cuenta técnica demo-rentabilidad-sin-conexion, contexto, SKU/publicación/variante, cantidad única, fecha posterior al congelado, costo y previsión exactos y reproducción del motor/piso.
- No se abre la importación a cuentas conectadas ni se certifica la cuenta/publicación declaradas. Una huella comprueba coherencia, no autenticidad de archivos externos.
- En paquetes enlazados se exige cobrador MP igual al vendedor ML declarado y aprobación no anterior a las órdenes vinculadas. Otros alcances requieren revisión, no fallback. Los contratos históricos sin enlace conservan su comportamiento previo.
- MP conserva los pendientes del lector ML, además de agregar sus propios faltantes; no borra la advertencia de vínculo declarado.

Cobro, resultado y mínimo:
- Se distinguen neto del detalle económico, neto MP menos gastos locales informados y previsión congelada. Retenciones no se convierten automáticamente en otro costo de producto.
- Con cobro coincidente, el cargo ML contrastado por MP recibe otra fuente del mismo hecho. No se suma otra comisión ni envío. El embalaje local se descuenta una vez; si ya integra costo, no se agrega de nuevo.
- Sin net_received_amount, el cobro y su neto después de gastos locales quedan pendientes. El importe bruto no los reemplaza.
- Si comisión/envío difieren entre ML/MP, el resultado económico del detalle continúa parcial. No se agrega la diferencia al gasto para forzar una conciliación ni se afirma que la previsión se cumplió.
- Falta de contraste MP, cargos sin vincular, importe de pago diferente, neto sin reconstrucción consistente, gastos estimados o faltantes básicos de comisión/envío/embalaje/cargo llevan el enlace a requiere_revision. El aviso deja explícito que no se confirma el mínimo.
- En ese estado se suprimen las diferencias económicas frente al previsto y al mínimo (null/Pendiente), para evitar un aparente $0 de desvío mientras los hechos siguen sin resolver.
- Con contraste coincidente pero envío efectivamente mayor en el ensayo, la alerta bajo mínimo se conserva; no se ajusta la previsión después de observar el gasto.
- Impuestos, fuentes externas y demás conceptos no acreditados continúan pendientes. Incluso un contraste coherente es provisional y publicacion_habilitada/definitivo continúan false.

Verificación:
- 398 pruebas focalizadas aprobadas: 281 del bloque anterior, 86 regresiones existentes de lectura ML/MP añadidas a la ejecución y 31 casos nuevos (27 de integración de snapshots y cuatro de ruta).
- Pruebas del recorrido completo costo/previsión → paquete → lectores → analizador: importes UAT con embalaje $100/$500, envío mayor, modos incluido/sin costo, neto faltante, comisión diferente, fuentes duplicadas no sumadas, gastos locales efectivamente distintos, descarga/relectura raw y normalizada.
- Rechazos por vendedor/cobrador, fechas de pago/orden, SKU/publicación/variante/cantidad, costo/previsión/huella y contexto ajenos. Sin verde para neto/detalle de cargos MP ausentes, comisión ML ausente o embalaje estimado.
- Ruta real extraída por AST ejecutada por HTTP Flask y plantilla real con dobles de ORM/acceso; incorpora los tres casos, descarga y relectura del JSON renderizado. No sustituye middleware real de autenticación/CSRF ni pruebas PostgreSQL.
- Compilación Python y sintaxis JavaScript aprobadas. Sin suite completa, arranque de app/scheduler ni revisión visual de navegador.
- Sin cambios a app.py, modelos, migraciones, bootstrap, flags, credenciales, estados, webhooks, producción ni conexiones nuevas. Cero ventas, movimientos financieros, stock, reservas, cobros o publicaciones operativas.

UAT agrupado tras desplegar:
1. Costos y precios → 5. Políticas comerciales → Gestionar UAT-PROD-001 → Preparar venta de prueba. Mantener Gastos según lo previsto.
2. Desplegar Contrastar el cobro ML + MP de este producto. Cobro y cargos coincidentes → Contrastar cobro y cargos. Debe conservar los importes; con embalaje $500 actual, neto después de gastos locales $5.921,50, costo $4.933,65 y resultado parcial $987,85. La sección Contraste de cobros y cargos MP debe mostrar los grupos coincidentes y no otro descuento.
3. MP sin neto informado: cobro/neto pendiente, aviso requiere revisión y comparación frente al mínimo pendiente.
4. MP con $100 más de comisión: cargo con diferencia, neto cobrado $100 menor, comparación pendiente; el detalle ML no recibe otro descuento automático.
5. Descargar paquete ML + MP del producto del último caso y analizarlo en el formulario offline de la misma pantalla; debe conservar fuentes/diferencia/pendientes, sin cambiar costo o previsión guardados.

Pendientes conservados:
- No se considera terminada la importación de operaciones reales ni la conciliación completa de cuenta/liberaciones/transferencias/contracargos/reintegros MP. Sin saldo disponible consultado.
- Falta el circuito operativo con producto físico, fabricación, venta/envío reales, todas sus deducciones documentadas y snapshot aprobado antes de vender. No cargar todavía el nuevo producto integral.
- Packs, más unidades, mayoristas y varias cuentas/variantes no se deducen del caso de una unidad; siguen pendientes de su vínculo explícito. Continúa el resto del plan y los pendientes históricos no revalidados.


## 2026-10-19 — Nuevo orden de trabajo y Base de Datos en la barra lateral

Decisión explícita de Martín:
- Avanzar por partes para simplificar el recorrido, empezando por creación de productos manual o masiva y ordenando el mapa del sitio.
- Nuevo principal Base de Datos, con secundarios en este orden: Productos, Proveedores, Clientes.
- Se pospone la continuación del bloque fabricación → costo obtenido hasta ordenar/revisar el alta de productos. No iniciar otro desarrollo financiero en paralelo ni cargar aún el producto integral.

UAT del bloque ML/MP anterior:
- Captura 203000: contraste coincidente, neto cobrado menos gastos locales $5.921,50; costo $4.933,65 y resultado parcial $987,85. Diferencia frente al previsto cero y frente al mínimo $0,50.
- Captura 203016: MP sin neto informado, cobro pendiente; diferencia frente al mínimo Pendiente y frente al previsto No disponible.
- Captura 203031: MP con $100 más de comisión, neto cobrado menos gastos locales $5.821,50; detalle ML conservado como parcial y comparación pendiente, sin otro descuento automático.
- Captura 203207: relectura del paquete ML/MP conserva cobro $5.821,50, fuentes y pendientes. Se cierra ese UAT específico de tres casos y relectura; no se declara operación real ni cobertura completa de MP.

Navegación implementada:
| Ruta natural | Destino existente reutilizado | Alcance |
| --- | --- | --- |
| Base de Datos → Productos | admin_productos.panel | Maestro tenant actual, con entradas manual y Excel existentes. |
| Base de Datos → Proveedores | admin_compras.panel?vista=proveedores | Solo maestro de proveedores, alta y gestión existentes; acceso a importación y enlace Abrir Compras. |
| Base de Datos → Clientes | admin_crm.panel?vista=clientes | Maestro de clientes e identidades de canal existentes; enlace Abrir CRM. |

- Se reutiliza details/menu-group/menu-children del menú actual. Grupo abierto y opción activa al visitar un hijo. Productos deja de estar duplicado como principal independiente.
- Base de Datos conserva visibilidad admin; no amplía permisos a Carga/Despacho. Los manejadores mantienen autenticación, resolución de tenant y controles actuales.
- Administración → Tesorería y Contabilidad se mantienen como estaban aceptados. Compras y CRM completos conservan sus accesos y funciones; solo los accesos desde Base de Datos muestran la vista de maestro.
- Proveedores no muestra órdenes, recepciones, facturas, mapeos o propuestas en esta vista. Clientes no muestra etapas, oportunidades o actividades. No se duplica una tabla, modelo o formulario de negocio: se reutilizan las plantillas y servicios originales.
- Guardar desde cada vista conserva su destino tanto en éxito como en error. Solo se admiten valores de vista conocidos, no URLs de retorno externas. Cancelación y diálogos usan los controles existentes.
- Importar proveedores conserva el proceso existente y vuelve a Proveedores, con la misma sección lateral activa.
- Este cambio de presentación no modifica consultas, altas, importaciones, validaciones de datos, estados o activaciones de los maestros.

Verificación:
- 25 verificaciones locales de render/navegación y retorno: menú en los cuatro destinos, orden, opción activa, ausencia de Productos duplicado, visibilidad por rol, vistas completas frente a vistas de maestros, clientes con/sin registros y retorno de éxito/error de los manejadores reales extraídos por AST con servicios simulados.
- 12 pruebas existentes de Compras/CRM aprobadas. Una prueba de composición de app.py no se ejecutó en el checkout reducido; app.py/bootstrap no cambiaron. Se actualiza únicamente el delimitador de extracción del fragmento Proveedores en la prueba existente para que tolere la condición de presentación.
- Compilación Python aprobada. Render con Flask/Jinja real y dobles de datos, sin escrituras de DB, arranque del sistema ni inspección visual de navegador. No se repiten las 398 pruebas económicas por este cambio de navegación.
- Sin cambios a modelos, servicios de dominio, scheduler, webhooks, credenciales, flags, conexiones, stock, pagos o producción. No se crean productos, proveedores o clientes durante la verificación.

UAT acotado tras desplegar:
1. Abrir Base de Datos y verificar orden Productos / Proveedores / Clientes.
2. Productos: comprobar que abre el maestro actual y se ven las opciones manual y masiva; no cargar todavía un archivo ni producto.
3. Proveedores y Clientes: comprobar que abren sus maestros, sin el resto del circuito de Compras/CRM, y conservan la barra lateral y opción activa.
4. Los enlaces Abrir Compras/Abrir CRM permiten volver a las pantallas completas.

Siguiente trabajo, según la nueva prioridad:
- Revisar el alta manual y la importación masiva de productos, qué campos pertenecen al maestro único y cómo se enlazan luego con ficha comercial, fabricación y costo. Auditar las validaciones y evitar duplicar el producto por completar su ficha.
- La vista Productos actual corresponde al maestro interno/logístico. La existencia de botones no acredita que toda la creación integral y masiva esté aceptada; su presentación y flujo se revisarán en el siguiente bloque antes de pedir nuevas cargas.
- Conservar todos los pendientes históricos y la separación staging/producción. Este ajuste del mapa del sitio no habilita el producto integral ni cierra los pendientes de fabricación o cuentas reales.


## 2026-10-19 — Regla de fuente principal: ficha maestra única de Productos

Decisión explícita de Martín:
- Productos deja de entenderse como una lista exclusivamente logística: será la base principal de la que se nutran todos los procesos, funciones y cálculos vinculados a productos.
- Se reutiliza Producto y su identidad por organización. No se crea un segundo maestro comercial, productivo o logístico ni se duplica un producto para completar datos de otro módulo.
- La creación manual y masiva deben alimentar la misma estructura y utilizar las mismas validaciones. La carga masiva debe presentar su previsualización y diferencias antes de confirmar.
- La ficha debe reunir identificación/clasificación, características e imágenes/variantes, fabricación/compra/combo, proveedores, unidades/presentaciones, inventario, costos, condiciones comerciales/publicaciones y logística/embalaje.
- Se permite alta en borrador con datos básicos. La completitud y elegibilidad se validan para cada uso; un borrador no queda automáticamente listo para fabricar, vender, publicar o despachar.

Criterio de integración:
- Los datos propios e intrínsecos del producto se administran desde la ficha principal. Las rutas actuales de módulos deben reutilizar esa identidad y las referencias correspondientes.
- Catálogos, listas, cuentas, proveedores y variantes se vinculan explícitamente; no se elige arbitrariamente la primera asociación cuando haya varias.
- Condiciones por organización/unidad, catálogo/canal y vigencias mantienen su alcance. Centralizar el acceso no significa convertir precios, costos o disponibilidad de distintos contextos en un único valor global.
- Stock, reservas, compras, producción, ventas, envíos y cobros conservan sus registros/transacciones. La ficha presenta su información vinculada, sin inventar saldos editables ni copiar movimientos.
- Las versiones de costo y snapshots históricos de ventas/publicaciones deben conservar sus datos originales. Editar la ficha actual no recalcula ni reescribe hechos anteriores.
- Cambios de datos que afecten composición, costo, embalaje o política deben aplicar los controles existentes de vigencia/obsolescencia antes de presentar un precio como cumplido.
- Se distinguen características físicas del producto de medidas/peso del paquete y condiciones de envío. Los permisos logísticos existentes no se reemplazan por defaults de una importación de datos generales.

Auditoría inicial:
- Producto actual contiene identidad tenant y datos logísticos. La pantalla /admin/productos sigue centrada en esos campos.
- CatalogoProducto ya conserva nombre/marca/categoría/descripciones/características, medidas propias del producto, imágenes, atributos, variantes, relaciones y datos comerciales por catálogo.
- PerfilCosteoProducto ya clasifica simple/producción/combo por contexto y vincula composición; existen versiones de costo, inventario y trazabilidad económica.
- La ruta masiva actual del maestro delega directamente la sincronización Excel. Su presencia no acredita previsualización del nuevo contrato integral ni preservación de todos los campos ausentes.
- Debe revisarse la propiedad de cada dato y adaptar esas rutas/servicios. No volcar todas las tablas en un JSON único ni reemplazar los módulos existentes por otro conjunto de maestros.

Estado:
- Esta sección registra la decisión de arquitectura y el alcance confirmado; no declara implementada la ficha maestra integral.
- Siguiente desarrollo: organizar la ficha y los campos con sus fuentes existentes, resolver datos generales faltantes y adaptar alta manual/masiva con preservación de relaciones e históricos.
- Todo se prepara en integración/staging. Sin cambios a producción, flags o conexiones, sin nuevas cargas de productos ni migraciones ejecutadas por esta definición.


## 2026-10-19 — Planilla real como referencia del maestro y usos combinables

Solicitud de Martín:
- Tomar PLANILLA GENERAL(2).xlsm como referencia de los campos y relaciones necesarios. El mismo producto puede venderse individualmente, participar en combos y utilizarse como insumo, incluidos usos simultáneos.
- Esta precisión complementa la ficha maestra única anterior. No equivale a importar automáticamente el libro ni a ejecutar sus macros.
- Fuente inspeccionada en lectura: SHA-256 d0e9bcfc86a287f66e3c7715e5421b9d5a853ad466335a00158cec30f0fba095. Libro original conservado. Comparación con código oficial de integración 309db38fffd8a877edb387939c30d50fe4b8fe08.

Relevamiento verificable:
- 14 hojas. Productos tiene 372 filas con ID informado, 371 IDs distintos; Línea contiene Laser y Herrería.
- Productos!A1:E1: ID Producto, Nombre, Línea, Descripción, Activo (Sí/No). Nombre y descripción son datos diferentes y deben preservarse.
- Componentes!A1:L1: producto padre, código de proveedor, nombres consultados, descripción de la pieza/uso, medida en cm, cantidad, unidad, total calculado, rendimiento por placa, tiempo de 1/4 de placa y cantidad por cartón.
- Insumos!A1:G1 resume consumos y costos por producto/código de proveedor. Sus cantidades y nombres provienen de Componentes y Lista Proveedores; no es otro maestro independiente.
- Lista Proveedores!A1:G1 contiene código del artículo del proveedor, nombre de insumo, proveedor, unidad, precio, bulto y lista. Ese código no identifica por sí solo a la persona/proveedor ni reemplaza el SKU interno.
- Tareas!A1:C1 vincula producto, tarea y segundos. Sueldos y Costos Laser aportan las tarifas y parámetros compartidos. No copiar sueldos, cotización o vida útil a cada ficha.
- Resumen Producto reúne resultados y supuestos; Lista Laser, Lista Herreria y Consulta Componentes son vistas derivadas. Calculo Competencia contiene escenarios de cargos/descuentos/precios; no acredita consultas reales de competidores. Utilidades mdf tiene un código y detalle, con utilidad vacía en la fila existente.

Mapa de propiedad de datos y brechas:
| Fuente/campos de la planilla | Destino funcional desde Productos | Base existente y adaptación requerida |
| --- | --- | --- |
| Productos: ID, Nombre, Línea, Descripción, Activo | Identidad estable por organización, nombre interno, línea/clasificación, descripción y estado general | Producto tiene SKU y una descripción, sin nombre/línea/activo propios. CatalogoProducto tiene nombre y estados comerciales por catálogo; no usar el primer catálogo como fuente general automática. Completar la ficha general y resolver diferencias explícitamente. |
| Usos simultáneos indicados por Martín | Vendible individualmente y utilizable como insumo, con pertenencia a combos mediante relaciones | Falta contrato común de usos. No confundirlo con PerfilCosteoProducto.tipo ni ItemInventario.tipo. No deducirlo de que una fila esté en una hoja. |
| Componentes: producto, componente, descripción, cantidad, medida, unidad y rendimientos | Composición del producto, consumo por unidad, conversiones/rendimientos y notas de operación | ProductoInsumoCosteo ya relaciona perfil e insumo con cantidad/merma; ComboProductoComponente relaciona perfiles con cantidad. Reutilizar esas estructuras, completar parámetros que no están representados y el vínculo al producto maestro cuando el componente también sea vendible. |
| Lista Proveedores: artículo, proveedor, unidad, bulto, precio/lista | Proveedores vinculados, códigos externos, presentación de compra y costo con moneda/vigencia/base de impuestos | Reutilizar ProveedorCompra, InsumoProductivo e InsumoPrecioVersion. No identificar por nombre ni crear otra persona/proveedor por cada artículo. Verificar vínculo explícito y alcance antes de migrar; no atribuir al modelo actual equivalencias que todavía no tiene. |
| Tareas: tarea y segundos | Ruta/operaciones y tiempo por producto | ProductoOperacionCosteo y ProductoMaquinaCosteo ya manejan minutos y orden. Convertir segundos/minutos explícitamente, sin asumir que Tiempo 1/4 placa tiene la misma unidad que Tareas. |
| Sueldos y Costos Laser | Recurso laboral, máquina, consumibles, amortización y tarifas vigentes vinculadas | Reutilizar fuentes laborales y maquinaria existentes. Evitar doble imputación si una tarifa de máquina ya incluye mano de obra. |
| Resumen Producto: costo, margen, impuestos, comisiones y precios; Calculo Competencia | Costos versionados y simulación comercial por contexto, accesibles desde la ficha | Reutilizar motor y versiones de costo, reglas económicas y simulación ML. Los importes calculados no son campos generales editables ni precios universales. |
| Medidas/embalaje/permisos logísticos actuales; ficha comercial existente | Secciones de características y logística de la misma identidad | Conservar datos actuales. Separar producto físico, pieza consumida, rendimiento de placa/cartón y paquete de envío. No inventar estas equivalencias a partir de Medida Cm. |

Regla de identidad y roles:
- Un producto conserva un único producto_id y SKU interno por organización aunque se venda, se fabrique, integre un combo y se consuma en otra fabricación.
- Ser insumo es un uso del artículo material, no exige una copia con otro SKU. Servicios productivos y recursos laborales no se convierten automáticamente en productos inventariables.
- Ser componente de un combo no convierte al componente en combo. Un combo tiene composición propia y también puede venderse o utilizarse como componente de otra estructura válida.
- La estructura de costeo simple/producción/combo se mantiene diferenciada de la habilitación comercial y del uso como insumo. No cambiar el tipo de costeo para habilitar venta, ni marcar insumo borrando venta.
- InsumoProductivo actual es una entidad separada sin producto_id; existe MapeoInsumoInventario y el SKU de ItemInventario apunta a Producto. Ese enlace cubre contextos de inventario, pero no acredita todavía un contrato universal producto/insumo de doble uso. Resolver su adaptación sin duplicar identidad, stock ni costo.
- Deben validarse tenant/unidad, unidades de compra/consumo/stock, cantidades positivas, conversiones explícitas y ciclos directos o indirectos entre composiciones. El costo de un subproducto se toma de su versión correspondiente, sin volver a sumar los insumos ya incluidos.
- La centralización no altera reservas ni movimientos ni reescribe costos o ventas históricas. Un cambio relevante deja pendientes las revisiones de costo/precio que correspondan.

Observaciones para importación:
- Productos!A153 y A340 repiten CJ-MDF-000 con nombres/descripciones diferentes. Bloquear ese conflicto en previsualización, mostrando ambas filas. No elegir primera/última ni fusionar por similitud. No se corrigió el libro.
- Los códigos padre de Componentes, Insumos, Tareas y Resumen Producto se encuentran en Productos; los códigos de componente consultados en Componentes/Insumos se encuentran en Lista Proveedores. Esto verifica referencias por código, no precisión de fórmulas, costos o unidades.
- Productos e insumos del libro usan espacios de códigos distintos; no hay coincidencia entre IDs de Productos y códigos de Componentes. No demuestra ausencia del uso doble: esa capacidad viene de la regla explícita de Martín, no debe inferirse por coincidencias de códigos.
- Componentes!I calcula consumo: cm a metros, cantidad/rendimiento por placa o cantidad/cartón según datos presentes. Preservar parámetros y unidad, no copiar el Total calculado como dato manual sin trazabilidad.
- Resumen Producto!H2 usa F2*(1+G2): el campo Margen % representa recargo sobre costo en esa fórmula. No es el margen sobre precio de venta de N2. La carga y la interfaz deben distinguir recargo, rentabilidad y mínimo neto, conservando la regla de precio ML ya acordada.
- Lista Proveedores tiene fórmulas que quitan IVA en algunas filas y en otras solo dividen lista/bulto. No aplicar IVA fijo a toda la importación ni asumir importes netos homogéneos. Requieren base tributaria explícita.
- Hay notas y cálculos auxiliares sin encabezados en Lista Proveedores!H:R. No transformarlos en campos generales por posición. Las fórmulas que dependen de posición de fila tampoco reemplazan relaciones por identidad.
- No importar fórmulas como valores confirmados por tener un resultado cacheado. Si faltan parámetros, vigencia o resultado verificable, mostrar pendiente. No tratar un vacío como cero.
- Alta manual y masiva deben compartir contrato y validaciones; columnas ausentes conservan datos actuales. Borrado de un dato requiere acción explícita, previsualización de diferencias y confirmación normal con popup, sin frase escrita.

Siguiente bloque concreto:
1. Completar la ficha general en Base de Datos → Productos con nombre, línea, descripción, estado, unidades y usos combinables. Reutilizar SKU e identidad existentes.
2. Mostrar desde Gestionar las secciones vinculadas de proveedores, composición, tareas, costos, características y logística; seleccionar contexto cuando haya más de uno, sin nuevos maestros paralelos. Diálogo compacto, secciones plegables y acciones consistentes.
3. Adaptar alta manual e importación masiva de los campos generales con previsualización, errores por fila y preservación de relaciones/datos omitidos. La planilla completa sirve de referencia, no se envía al importador logístico actual como si ya fuera compatible.
4. Resolver con migración explícita y reversible el vínculo artículo/insumo y los datos generales faltantes; verificar esquema antes de cambiar consultas. No depender del bootstrap deshabilitado ni repetir un despliegue que consulte columnas inexistentes.
5. UAT inicial en staging: mismo artículo vendible/insumo, componente usado en combo sin duplicarlo, combinación comprada/fabricada con estructura explícita, duplicado CJ-MDF-000 rechazado, reimportación sin cambios, columna omitida preservada y cancelar sin guardar. Después continuar con fabricación/costos del caso integral.

Estado: relevamiento y contrato registrados. No se declara implementada la ampliación del maestro, no se importó el libro ni se ejecutaron macros, migraciones, altas o movimientos. Este registro no requiere deploy de aplicación. Producción y conexiones quedan fuera del cambio.


## 2026-10-19 — Primer bloque implementado del maestro APB: tipo y cuatro habilitaciones

Alcance autorizado por Martín:
- Aplicar desde Productos un tipo excluyente (simple, producción, combo) y cuatro casillas independientes: compra, venta, insumo de producción y componente de combo.
- Priorizar carga/lectura prácticas, ventanas de gestión, consistencia visual, secciones plegadas y ajustes posteriores sobre el resultado. No retomar aún el producto integral de fabricación.

Implementación:
- La identidad sigue siendo Producto. ProductoFichaMaestra es su extensión 1:1, con producto_id como clave primaria y FK; no tiene otro SKU ni crea otro producto. Conserva nombre, línea, unidad, tipo, estado y cuatro booleanos independientes. Descripción y logística conservan sus columnas y vínculos actuales.
- No se agregan columnas a Producto ni se altera su SELECT operativo. El esquema nuevo se detecta antes de consultarlo; si falta, Productos muestra lectura y aviso de preparación pendiente, sin errores por columnas inexistentes ni escrituras parciales.
- La extensión se prepara explícitamente en staging; no se usa bootstrap ni se modifica su flag. El script no importa app.py ni inicia scheduler/jobs y no asigna tipo/roles a productos anteriores.
- Un producto existente sin extensión figura Sin configurar. Si todos sus perfiles tienen un único tipo se muestra ese antecedente; los roles no se infieren de códigos, nombres o posición en una hoja. Los consumidores heredados mantienen su comportamiento mientras no exista una ficha configurada: no equivale a una aprobación de sus cuatro usos.
- Los cuatro usos son combinables para cualquiera de los tres tipos. Producto inactivo bloquea los nuevos usos controlados aunque conserve sus casillas; no se eliminan composiciones ni hechos históricos.
- SKU existente de solo lectura en esta ficha, alta por SKU normalizado y control de duplicados dentro de la organización. Huella de datos y bloqueo de fila para no pisar cambios de otra pestaña, incluyendo cambios hechos por los servicios logísticos anteriores.
- Tipos de perfiles y maestro se validan en ambos sentidos. Una ficha con perfiles de tipos diferentes no se transforma silenciosamente: se rechaza el cambio y se pide revisar las composiciones. No se cambia el modelo de costos ni se crean perfiles/costos automáticos.
- Referencia opcional al InsumoProductivo físico existente, de la misma organización y unidad de medida explícita. La referencia es única y se conserva tras guardarla; el producto puede tener simultáneamente venta e insumo habilitados. No se copian precios o saldos ni se fabrican identidades por coincidencia de códigos.
- Esta referencia no convierte por sí sola un ItemInventario de producto en insumo ni habilita stock compartido para una identidad de inventario aún no preparada. La adaptación integral del doble uso en todos los selectores y su circuito físico sigue pendiente de UAT y del vínculo correspondiente. Se conserva la precisión/conversión existente.

Pantalla:
- Base de Datos → Productos conserva base.html y la barra lateral. Listado compacto con SKU/nombre, línea, tipo, usos, estado y Gestionar; se elimina la edición horizontal con numerosos inputs.
- Nuevo producto y Gestionar comparten un diálogo. Datos generales y casillas visibles; referencia de insumo/costeo y logística plegadas inicialmente. Se reutiliza la paleta y las clases comerciales, con estilos acotados de Productos.
- Búsqueda por SKU, nombre, descripción o línea; hasta 100 resultados. No se carga una ficha por cada fila ni se hacen 100 consultas de perfiles: las fichas y tipos se leen por lote.
- Cancelar y cerrar son botones type=button sin POST. Reabrir recupera los valores guardados. Enter en inputs no envía; el guardado abre una reconfirmación con Cancelar/Confirmar, sin escribir frases. Enter en esa reconfirmación no la acepta de forma accidental.
- Conserva CSRF, tenant y acceso admin; la descarga de plantilla aplica la misma autorización. Errores de validación reabren los valores ingresados. Se bloquea doble envío de la interfaz y se conserva la posición de scroll después de guardar.
- Esta pantalla no ofrece eliminación física: el estado y los usos permiten deshabilitar sin borrar relaciones. Un POST con la acción antigua eliminar_producto se rechaza.
- El estilo fue verificado por estructura y render de las plantillas reales, sin afirmar aceptación visual de Martín. No se completó inspección en Chromium: la descarga del navegador del entorno devolvió un archivo inválido. El control visual final corresponde al UAT de staging.

Importación desde Productos:
- XLSX/XLSM/CSV, máximo 2 MB y 500 productos. Hoja Productos si existe, o primera hoja. No ejecuta macros; fórmulas no se aceptan como datos editables.
- Plantilla CSV descargable con datos de ejemplo y los cuatro usos explícitos. La antigua importación directa de esta pantalla se reemplaza por previsualización, diferencias antes/después y confirmación con popup.
- Alta manual y lote comparten normalización y validación. Columnas/celdas vacías del lote conservan datos actuales; No/0 destilda explícitamente. Los nuevos productos o anteriores sin configurar exigen estado y cuatro usos explícitos, tipo y unidad: no se habilitan por defaults.
- Un SKU duplicado se rechaza en todas sus filas; un error impide aplicar el lote completo. La firma incluye organización y usuario, vence a los 15 minutos y se revalida contra las huellas actuales. Lote atómico, rollback ante cualquier conflicto, sin borrar productos ausentes.
- La planilla de Martín no se importó. Su CJ-MDF-000 repetido sigue siendo un conflicto para revisar, no una corrección automática.
- Los importadores existentes de catálogos y fuentes de costo mantienen sus contratos especializados; este bloque no declara transformados todos los importadores anteriores en el nuevo contrato general.

Controles conectados en este bloque:
| Uso/regla | Puntos controlados | Conservación |
| --- | --- | --- |
| Tipo maestro | crear_o_actualizar_perfil y guardar ficha manual/masiva | Sin reclasificar perfiles ni reescribir costos históricos. |
| Componente | agregar_componente_combo y crear_o_actualizar_componente_combo | Rechaza nueva selección/edición de componente deshabilitado; conserva líneas existentes. Sigue la restricción actual de no anidar combos. |
| Venta | Agregar a catálogo, activar/disponibilizar ficha comercial, aplicar inclusiones masivas y cálculo interno de cantidad publicable | Sin publicar, conectar cuentas, cambiar precios ni ventas históricas. |
| Compra | Crear orden y agregar ítem cuando el insumo tiene vínculo verificado al producto | Sin órdenes ni importes reales; las líneas de texto sin identidad de producto no se atribuyen por suposición. |
| Insumo | Guardar línea de insumo en ficha de producción, con referencia directa o mapeo de inventario verificado | Sin consumos, stock ni precios nuevos. |

Los controles anteriores no acreditan cobertura universal de los consumidores operativos antiguos. No se tocaron importación real de pedidos/ventas, webhooks, automatismos ni reglas de transporte. Quedan pendientes la adecuación progresiva de sus selectores y la revalidación al confirmar operaciones preparadas previamente, sin impedir incorporar hechos externos reales.

Verificación:
- 21 pruebas nuevas con Flask/SQLAlchemy/SQLite y plantillas reales: ausencia de esquema, preparación idempotente, productos previos conservados, cuatro usos, deshabilitación e inactividad, valores inválidos/no finitos, checkbox ausente, tenant, SKU estable, edición obsoleta, tipo compatible con costeo, componente bloqueado, compra/consumo rechazados en manejadores reales, catálogo/disponibilidad bloqueados, referencia única, lotes duplicados, rollback atómico, firma/usuario/organización, reimportación sin cambios, plantilla, fórmulas y ruta/CSRF.
- 25 pruebas existentes de perfiles, composición, DB de catálogo y administración aprobadas. Se excluyeron tres aserciones estáticas anteriores sobre un cache-buster y selector literal de JS de Fuentes de Costos que ya no coinciden con sus archivos originales; esos assets no se modifican en este bloque.
- 18 pruebas adicionales existentes de disponibilidad, inclusiones y compras aprobadas. Se eligió el alcance funcional disponible del checkout reducido, sin declarar ejecutada su composición monolítica ni las vistas no incluidas.
- Total: 64 pruebas aprobadas; sintaxis JS y compilación de los módulos modificados aprobadas. No se importó/inició app.py ni se utilizó una DB externa. No se declara verificado PostgreSQL/Render en ejecución ni aceptación visual en navegador.
- No se cambian main, flags, credenciales, conexiones, scheduler, estados operativos, inventario, pedidos, pagos o liquidaciones. Se mantienen los pendientes anteriores.

Preparación tras desplegar este commit en el servicio STAGING:
1. Shell de staging, en /opt/render/project/src: python -m scripts.preparar_ficha_productos --staging
2. El script exige laboratorio desconectado y rechaza otra rama/URL de Render cuando están informadas. Usa DATABASE_URL del servicio; no pedir ni pegar credenciales en el chat.
3. Resultado esperado: Ficha preparada. Productos existentes conservados, sin asignar tipos ni habilitaciones. Una segunda ejecución informa ya preparada y no altera datos.
4. Refrescar Base de Datos → Productos. No hace falta habilitar bootstrap ni cambiar flags.

UAT inmediato, por partes:
1. Revisar listado y abrir Gestionar de un producto conocido: identificación/logística previas conservadas y secciones complementarias plegadas. Cancelar sin guardar.
2. Nuevo producto ficticio UAT-MAESTRO-001: Simple, unidad, nombre; marcar las cuatro casillas. Cancelar, volver a abrir y comprobar que no se creó.
3. Repetir el alta, Guardar producto → Confirmar. Debe existir una sola ficha con cuatro usos. Destildar solo Venta y guardar; las otras tres casillas deben conservarse.
4. Editar una ficha en dos pestañas: el segundo guardado con datos anteriores debe mostrar aviso y no pisar el primero.
5. Descargar plantilla y revisar un lote de prueba antes de aplicar. SKU repetido rechazado, campos omitidos conservados y Cancelar importación sin cambios. No cargar todavía la planilla real.
6. Recoger observaciones de legibilidad/espacios/orden antes de ampliar características, proveedores, composiciones y navegación de la ficha. No iniciar aún el producto integral.


### Ampliación de referencia DUX recibida durante este desarrollo

Captura de Martín image(20261019-212841).png inspeccionada: Nuevo Producto, paso 1 de 6, muestra Simple / No Stockeable / Con Variantes / Combo / Producción / Trazable. Se toma como referencia de capacidades, sin convertir las seis tarjetas en un único selector excluyente ni reproducir obligatoriamente sus seis pasos.

- Se conserva la decisión de tres tipos: Simple, De producción y Combo, con las cuatro habilitaciones independientes.
- Se agregan al alcance siguiente de la ficha tres capacidades separadas: controla stock o no stockeable; tiene variantes; requiere identificación/seguimiento individual por número de serie. Pueden coexistir con el tipo y con sus usos.
- No stockeable significa que no se cuenta/almacena el artículo, por ejemplo un servicio. No significa stock cero ni control temporalmente desactivado. Su tratamiento debe respetar compras/ventas sin fabricar existencias, reservas, consumos o despachos físicos ficticios.
- Con variantes debe reutilizar las variantes comerciales existentes y su identidad de inventario, con SKU/atributos y existencia por variante cuando corresponda. No crear otra lista de variantes aislada en la ficha principal ni sumar stock de padre e hijos.
- Trazable en la captura refiere a número de serie por unidad para garantías/rastreo. No equivale al historial de movimientos, al lote de importación ni al LoteProduccion preparatorio actual. Se revisará el circuito completo de altas, recepción, fabricación, venta, devolución y garantía antes de habilitar la obligación de serie.
- CatalogoProducto ya conserva variantes y atributos; el inventario distingue ítems. LoteProduccion ya existe, retenido/preparatorio y sin impacto. La revisión de esos archivos no acredita un circuito individual por serie listo para operación.
- Estas tres capacidades adicionales se registran como siguiente ampliación funcional; NO aparecen como casillas operativas ficticias en este primer commit. El bloque entregado mantiene tipo, cuatro usos, estado, referencia de insumo, logística y alta/importación.
- Revisar el resultado de Productos primero y agregar esas capacidades con validaciones e integración de sus módulos. Esta nueva referencia no habilita conexiones ni el caso integral aún pendiente.


## 2026-10-19 — Sustituir el deploy pendiente: No stockeable y SKU propio de Combo

Aclaraciones de Martín, incorporadas al mismo bloque de Productos antes del despliegue:
- La denominación de la opción es exactamente No stockeable. No se llama sin stock: cantidad cero y ausencia de control de existencias son conceptos distintos.
- Un combo tiene otro producto y un SKU propio, diferentes de los artículos simples o de producción que lo componen. Los componentes conservan sus identidades y SKU; no se copian para usarlos en el combo.
- Se entrega un commit nuevo que incluye el bloque anterior y estas correcciones. No hace falta desplegar primero 36d60544dea16b028d2a8f2ed700fa0455669402.

Implementación:
- No stockeable es un booleano independiente en la extensión de Producto, visible en la ficha y en el listado. No agrega un cuarto tipo ni sustituye ninguna de las cuatro habilitaciones.
- Puede habilitarse para compra y venta sin inventario. La opción se persiste por alta manual o lote, con validación común; columna omitida conserva el valor existente. La plantilla agrega no_stockeable con Sí/No.
- En un producto No stockeable no se permiten permisos de envío físico. La interfaz los destilda y deshabilita; el servidor también valida y la importación informa el conflicto si recibe permisos de transporte habilitados. No se borran medidas ni datos anteriores por esta opción.
- Preparar ítems de catálogo omite los artículos No stockeables y sus variantes de inventario. Los caminos administrativos de alta/activación de existencias/SKU y el registro de movimientos los rechazan. Crear reserva controla el bloqueo antes de agregar la reserva o alterar saldos.
- Preparar materia prima desde una fuente ya vinculada a un producto No stockeable también se rechaza; no se elude la regla inventando un segundo SKU para esa identidad.
- Si el producto ya tiene una existencia, incluso en cero e inactiva, o un SKU de inventario activo, no se permite convertirlo a No stockeable. Se pide revisar historial/compromisos; no se desactivan controles, ajustan cantidades ni eliminan registros automáticamente.
- Los productos anteriores sin esta opción conservan el comportamiento previo. No se considera un saldo cero como evidencia para marcar No stockeable.
- El esquema sigue siendo aditivo y se detecta antes de leerlo. El mismo script de preparación crea la extensión completa o agrega no_stockeable con default FALSE a la versión inmediatamente anterior, preservando tipos y roles. Segunda ejecución sin cambios. No se habilita bootstrap.
- En ficha e importación se rechaza cambiar de simple/producción a combo o de combo a otro tipo conservando producto/SKU. El mensaje pide crear otro producto con SKU propio; en la ficha se deshabilita esa selección incompatible para productos ya configurados.
- Los perfiles de costeo también rechazan el cambio entre combo y otro tipo manteniendo el producto, aun sin componentes. Se conserva la restricción de SKU único por organización y de no autorreferencia.
- Marcar un simple como Componente de combo solo habilita su selección como componente: no lo convierte en combo ni cambia su SKU. Un combo nuevo se crea como otra ficha, con composición referenciada.
- Las ampliaciones de variantes y seguimiento individual por serie siguen pendientes. Este cambio adelanta No stockeable del alcance DUX; no declara implementado todo ese circuito.

Verificación y límites:
- 32 pruebas nuevas/acumuladas del maestro aprobadas: las 21 anteriores y 11 casos adicionales de No stockeable, envío, movimiento antes de mutar, omisión en preparación de SKU, preservación de inventario previo, actualización del esquema anterior, cuatro direcciones de cambio de tipo con Combo, SKU distinto de componentes y bloqueo de identidad duplicada desde la fuente de insumo.
- 25 pruebas anteriores de perfiles/composición/administración y DB de productos, 18 de disponibilidad/inclusiones/compras y 14 del núcleo de inventario y reservas/transferencias: 89 aprobadas en total.
- Se mantienen los mismos límites de checkout reducido, exclusiones de aserciones estáticas antiguas y ausencia de QA visual en Chromium documentados en el bloque anterior. Sintaxis JS y compilación Python aprobadas; sin ejecución en PostgreSQL/Render ni DB externa.
- No se importó la planilla real, no se crearon productos operativos ni se cambió main, flags, scheduler, conexiones, movimientos o dinero.

Despliegue/UAT:
1. Desplegar únicamente el nuevo commit en integración/staging.
2. Shell de staging: python -m scripts.preparar_ficha_productos --staging. Es el mismo comando para preparación inicial o actualización de la extensión anterior.
3. Base de Datos → Productos: nuevo artículo ficticio Simple con No stockeable y compra/venta habilitadas; guardar, reabrir, comprobar casilla y permisos físicos deshabilitados. No debe prepararse un SKU/existencia para él.
4. Crear otro artículo stockeable y un Combo con SKU diferente. El simple mantiene su SKU al seleccionarlo como componente. Intentar transformar la ficha existente de simple a combo debe quedar impedido; no probarlo sobre datos reales.
5. Revisar primero el orden visual y las casillas; conservar los demás pendientes y continuar por partes desde Productos.

## 2026-10-19 — UAT visual de Productos y corrección de alineación

Evidencia de Martín:
- Captura 221103: script de staging ejecutado; resultado Ficha preparada, productos existentes conservados y sin asignar tipos ni habilitaciones.
- Captura 221145: Base de Datos → Productos abre en staging con barra lateral, dos productos existentes, tipo De producción según costeo para UAT-PROD-001 y estados Sin configurar. Importación masiva plegada.
- Captura 221216: Nuevo producto abre en diálogo con No stockeable, tipo y cuatro usos; pie con Cancelar y Guardar producto. No acredita guardado ni aceptación final.
- Detectados en las capturas: Gestionar partido en dos líneas, checkboxes encima del texto en lugar de a la izquierda y franja vacía sobre SKU.

Corrección de presentación:
- La regla compartida .source-dialog form label:not(.resource-team-row) imponía orientación vertical con mayor especificidad que las clases locales. Se ajusta únicamente CSS de Productos para casillas horizontales, alineadas a izquierda, con medidas estables y sin alterar nombres/valores.
- La alerta interna vacía conserva hidden; se da prioridad visual a ese atributo para que .alerta display:flex no la haga aparecer. Un error real sigue mostrándose al quitar hidden.
- Columna de acciones con espacio para Gestionar, botón sin quiebre de palabra y ancho compacto. Se actualiza versión del CSS para evitar caché.
- Sin cambios de JS, modelos, migración, permisos, servicios o datos. No hace falta repetir la preparación de la ficha.
- Verificación: render de la ruta real con Flask/Jinja aprobado (1 prueba funcional existente); revisión de la cascada y especificidad de CSS frente a la regla compartida. No se repite la batería de 89 pruebas por este ajuste de presentación ni se declara QA visual de Chromium.
- La verificación final de alineación y altura queda pendiente de refrescar staging con Ctrl+F5 tras este commit. No cargar todavía la planilla real ni avanzar al caso integral.


## 2026-10-19 — Productos: Permitir stock negativo

Evidencia UAT anterior:
- Martín confirmó la cancelación del alta ficticia, el guardado de UAT-MAESTRO-001 y la independencia de Venta respecto de Compra/Insumo/Componente.
- Captura 222651: Producto de prueba, Simple, No stockeable, cuatro usos y Activo visibles en la lista. No acredita movimientos de inventario.
- A solicitud de Martín se incorpora Permitir stock negativo como atributo independiente de la ficha principal, sin crear otra política por SKU ni duplicar inventario.

Cambio:
- Casilla Permitir stock negativo en Nuevo/Gestionar, con la misma alineación; default FALSE, incompatible con No stockeable. Al marcar No stockeable la interfaz desmarca/deshabilita la nueva casilla y el servidor rechaza la combinación contradictoria, incluso en lotes.
- Misma regla para alta/edición e importación; la plantilla agrega la columna, las omisiones en actualizaciones conservan el valor y Sí/No explícitos lo cambian. Se incluye en huella de concurrencia y vista previa.
- El núcleo registrar_movimiento resuelve la autorización desde el producto del tenant; no recibe una autorización desde el formulario de movimientos. Sin ficha/autorización se mantiene el bloqueo anterior. Se serializa contra edición de la ficha mediante bloqueo del producto.
- Con permiso explícito, egresos y ajustes internos pueden dejar stock actual negativo o compromisos sin cobertura. Ingresos posteriores regularizan el saldo. Reservado/bloqueado nunca admiten valores negativos, liberar más de lo reservado sigue rechazado y nuevas reservas exigen stock disponible.
- No se permite destildar mientras alguna existencia del producto tenga stock negativo o compromisos sin cobertura. Se rechaza antes del guardado manual o del lote; no se corrigen saldos automáticamente.
- Un ajuste rechazado restaura el saldo en memoria antes de devolver el error. Los movimientos aceptados conservan evidencia anterior/nueva en el historial.
- No se modifica la configuración de automatización de pedidos: conserva su prohibición de stock negativo, ni se cambia el cálculo/publicación de disponibilidad. El permiso no habilita conexiones ni ventas automáticas.
- Preparación aditiva e idempotente: el mismo comando agrega permitir_stock_negativo BOOLEAN NOT NULL DEFAULT FALSE; conserva fichas, roles y valores previos. Entre deploy y preparación las guardias anteriores de Venta/No stockeable siguen vigentes leyendo solo columnas existentes; el permiso nuevo se considera FALSE. La edición ampliada queda deshabilitada hasta preparar.
- Alcance de pruebas: SQLite aislado y servicios comunes, no PostgreSQL/Render ni conexiones reales. No se declara validación visual de navegador para esta casilla antes del UAT.

Verificación:
- 36 pruebas del maestro (32 anteriores + cuatro de permiso/preservación/importación, compatibilidad antes de migrar, movimientos reales aislados/regularización/tenant y ruta real de casilla).
- Tres casos adicionales del núcleo: egreso/ajuste/recuperación explícitos, reservas/publicable/bloqueado y restauración del ajuste rechazado. Batería anterior del maestro, perfiles, composición, compras, disponibilidad y núcleo/reservas/transferencias aprobada; se conservan las exclusiones estáticas antiguas documentadas, sin afirmar ejecución del monolito.
- Sintaxis JS y compilación de módulos Python aprobadas.

Deploy/UAT pendiente:
1. Desplegar este commit solo en integracion-saas-2026-09.
2. Shell de staging: python -m scripts.preparar_ficha_productos --staging.
3. Base de Datos → Productos → Gestionar UAT-MAESTRO-001: actualmente No stockeable. Destildarlo, marcar Permitir stock negativo, guardar/confirmar y reabrir; verificar persistencia sin cambiar tipo ni cuatro usos.
4. Sin guardar, marcar No stockeable: la nueva casilla debe quedar desmarcada/deshabilitada. Cancelar y reabrir debe conservar la configuración guardada del paso anterior.
5. Movimientos con saldo insuficiente y regularización: pendientes de UAT en un inventario ficticio aislado; no ejecutar sobre existencias reales. No importar todavía la planilla real.


## 2026-10-19 — Combo completo desde el maestro de Productos

Corrección solicitada por Martín:
- El paso de UAT propuesto creaba primero un Combo sin elegir componentes. Martín rechazó ese flujo: el alta debe permitir elegir productos y cantidades, y no debe guardar un combo vacío.
- Se reemplaza esa instrucción. No se da por creado ni validado UAT-COMBO-001 por la respuesta anterior.

Implementación:
- Al seleccionar Combo, Nuevo/Gestionar muestra una sección de productos componentes con selector de SKU/nombre/unidad, cantidad y Quitar; botón Agregar componente. Se exige al menos una fila completa con cantidad positiva, finita, con hasta seis decimales y dentro del rango Numeric(18,6).
- Se ofrecen productos del tenant con ficha activa, Simple/De producción y Componente de combo habilitado. El servidor vuelve a comprobar identidad, tipo, uso, actividad y cantidades; no confía en las opciones del navegador. Rechaza duplicados, autorreferencia, otro combo, SKU inexistente/ambiguo y registros de otra organización.
- Reutiliza PerfilCosteoProducto y ComboProductoComponente, con los servicios existentes de Costos en modo sin commit intermedio. No crea otra tabla de recetas ni otra identidad para los componentes.
- El ámbito predeterminado es General. Si se elige una unidad de negocio del tenant se usa su perfil; los perfiles y composiciones de otras unidades se preservan. Solo se guarda la composición del ámbito seleccionado; la interfaz lo aclara.
- Reutiliza perfiles existentes sin cambiar su observación ni actividad. Crea los perfiles necesarios del combo/componentes cuando faltan en el ámbito elegido; no copia costos, rendimientos, operaciones ni recetas entre unidades.
- Producto, ficha, perfiles y componentes se guardan en una transacción. Validaciones principales antes del alta; cualquier fallo posterior revierte todo desde la ruta o el lote. Cancelar continúa sin POST y sin altas.
- Gestionar precarga la receta existente del ámbito elegido; cambiar cantidades o quitar filas actualiza esas mismas relaciones. No permite guardar la última fila eliminada. Las observaciones de componentes conservados no se borran.
- La huella del maestro incluye las composiciones por ámbito, también al configurar una ficha antigua: una modificación previa desde Costos invalida un formulario abierto. Lectura agrupada de perfiles/líneas para la lista, sin una consulta por cada producto.
- Importación del maestro: columna componentes_combo con formato SKU=2|OTRO-SKU=1 y unidad_combo_id opcional. Un alta Combo sin composición es rechazada en vista previa y en confirmación. Los componentes deben existir previamente; no se crean dependencias desde otras filas del mismo lote. En ediciones, columnas/celdas omitidas conservan el estado actual; cantidades se normalizan a seis decimales. Los cambios se muestran como SKU × cantidad y nombres de unidad, no como objetos internos.
- Los perfiles preparatorios anteriores de Costos no se eliminan ni rellenan por inferencia. Un combo antiguo vacío debe completarse al guardar su ficha en Productos; se identifica Completar composición en la lista. No se cambia el funcionamiento de los borradores anteriores del módulo de Costos.

Verificación:
- 49 pruebas del maestro aprobadas, incluidas 13 nuevas: nueve entradas inválidas sin alta parcial, reutilización/actualización/ámbitos/huella de Costos, tenant/roles/actividad/combo anidado, lote con composición obligatoria y rollback completo, ruta real y preservación del formulario ante error inducido.
- Cuatro casos anteriores que suponían crear un Combo vacío fueron adaptados para crearlo con componentes desde el inicio, conservando sus comprobaciones de tipos, usos y SKU propio.
- 25 pruebas anteriores de perfiles, composición, DB/administración de productos: 74 aprobadas en conjunto, con las tres exclusiones estáticas antiguas ya documentadas. Después de los ajustes finales de presentación, 25 casos relacionados con ruta, combos y lotes aprobados.
- Sintaxis JavaScript y compilación Python aprobadas. Render real Flask/Jinja en pruebas; sin QA visual de navegador ni ejecución PostgreSQL/Render. No se cambian inventario, canales, flags, scheduler, pagos ni producción.

Deploy/UAT:
1. Desplegar solo el nuevo commit de integración/staging. Este bloque no cambia el esquema ni necesita repetir preparación de ficha si ya está actualizado con Permitir stock negativo. Requiere las tablas de Costos ya existentes; si faltan bloquea el alta Combo.
2. Base de Datos → Productos → Nuevo producto: SKU UAT-COMBO-001, nombre Combo de prueba, tipo Combo, unidad unidad y Disponible para venta.
3. Debe aparecer la composición. Intentar guardar vacía debe impedir el alta con aviso visible; también se rechaza una petición sin componentes en el servidor.
4. Agregar UAT-MAESTRO-001, cantidad 2, ámbito General; guardar/confirmar y reabrir. Debe conservar cantidad 2 y SKU propio, usando las mismas relaciones de Costos. Si ya existe ese SKU, usar Gestionar para completarlo; no recrearlo.
5. Probar quitar la única fila: debe impedir guardar. Cancelar y reabrir conserva la composición anterior. No usar productos/existencias reales ni cargar todavía la planilla real.


## 2026-10-19 — UAT Combo y paso de cantidades

- Captura 233856: Gestionar UAT-COMBO-001 muestra UAT-MAESTRO-001 con cantidad 5 en Ensayo UAT. Martín aclara que eligió expresamente 5 unidades.
- Captura 234614: quitar el único componente muestra aviso de composición obligatoria. Martín confirma después la cancelación y conservación del valor anterior, y el bloqueo de componentes repetidos.
- Captura 000159 (nombre UTC del 20/10, fecha local 19/10): las flechas modifican la cantidad en millonésimas por el step 0.000001. La imagen sigue mostrando aviso de duplicados; no se da por validado el guardado de 5 a 3.
- Ajuste local de presentación/interacción: flechas con step 1. Para conservar cantidades decimales escritas manualmente y su validación HTML, la base mínima del step se alinea con su fracción actual; en enteros parte de 1. Se mantiene cantidad positiva y límite máximo. No se redondea ni transforma el valor escrito ni el guardado.
- Se actualiza versión JS/CSS y se agrega una ayuda breve junto a las cantidades. Sin cambios de modelos, servicios, transacciones, esquema ni datos.
- Verificación: sintaxis JS, render de rutas reales de Productos y prueba existente de receta con cantidad decimal. Pendiente UAT visual en navegador tras deploy. No requiere preparación de esquema.
- Próximo paso: en Gestionar UAT-COMBO-001 → Ensayo UAT, con una sola fila, probar flechas desde 5 (6/5/4) y guardar 3. Reabrir debe conservar 3. No asumir el guardado a partir de la captura del aviso.


## 2026-10-20 — Cierre del alta manual: ficha completa de Producto

Prioridad y evidencia:
- Martín pidió terminar Nuevo producto antes de seguir con otros módulos o procesos.
- Captura 121512: UAT-PROD-001 guardado como De producción, activo, Venta/Insumo/Componente; no acredita todavía una composición de fabricación nueva.
- Capturas 121658 y DUX 122235/122332/122354/122413/122434 revisadas. Se toman como referencia de campos y practicidad, conservando el diálogo, barra lateral, confirmación y secciones plegables de Fierro.
- No se incorporan saldos iniciales ni otro editor de costos/precios/listas en este alta: esos procesos ya tienen servicios propios. No se retoma todavía fabricación.

Alcance entregado:
- Clasificación del maestro: rubro, subrubro asociado a rubro y marca. Se ofrecen valores de la misma organización mediante sugerencias, con carga de valores nuevos en el mismo formulario. Se conserva Línea de la base anterior, sin reinterpretarla automáticamente como rubro.
- Proveedores: relaciones con ProveedorCompra, varios por producto, primero principal. Código externo/de proveedor opcional por relación; exige proveedor elegido. Código interno SKU independiente e inmutable.
- El código original conserva texto y ceros iniciales. Clave normalizada en mayúsculas con unicidad organización/proveedor/código; un mismo código puede existir en productos de distintos proveedores u organizaciones. Se rechaza reutilizarlo para otro producto del mismo proveedor. Proveedor repetido en la misma ficha rechazado. Sin código se permite relacionar el proveedor sin inventar una referencia.
- Sucursales y depósitos: dos habilitaciones explícitas sobre SucursalOperativa existente, que hoy reúne ambos tipos de ubicación. Una ubicación puede cumplir ambos roles; no se inventa una relación sucursal-depósito ni se usa UnidadNegocio como si fuera una sucursal física.
- Cada alcance tiene Definir habilitados. Sin definir conserva compatibilidad del sistema anterior; definido con lista vacía significa ninguno habilitado. No se crean ubicaciones, existencias, SKU de inventario ni movimientos al guardar.
- El depósito definido se valida al crear existencias desde ambas interfaces de inventario y al usar el acceso común para reservas/movimientos/controles. No permite retirar habilitación de un depósito con saldo/reservas/bloqueos/tránsito pendientes. Sucursales se registran como alcance del maestro, con guardia reutilizable para los procesos que reciban ubicación física; no se afirma convertidos todos los consumidores comerciales históricos.
- Utilidad pretendida opcional, con base Costo o Precio de venta. Vacío es Sin definir y cero es explícito. Sobre costo admite recargos mayores al 100%; sobre venta exige menos del 100%. Decimal finito, no negativo, hasta seis decimales.
- El porcentaje queda como objetivo del maestro. Se muestra ejemplo claramente ilustrativo sin gastos/impuestos (costo 100, 30% sobre costo → 130; sobre venta → 142,86). No se identifica margen sobre venta bruta con sobre_liquidacion de la regla económica existente.
- No se activa ni reemplaza una ReglaEconomicaVersion, lista o precio publicado al guardar el maestro. La aplicación del objetivo en cada cálculo/canal debe usar las fuentes y pisos verificados existentes; no se modifica el motor ni se debilita la regla insalvable del neto mínimo. Este bloque termina la captura manual de estos datos.
- Códigos de barras: varios por producto, texto con ceros iniciales, máximo 20; únicos por organización para evitar identificar dos productos. No se fabrican EAN ni se exige que todo código interno sea EAN.
- Imágenes: hasta cinco JPG/PNG/WEBP de 2 MB cada una, principal seleccionable, miniaturas, quitar/conservar y reemplazo. Reutiliza prevalidar_imagenes de la ficha comercial, suma límites de tamaño/resolución y comprueba formato real. No admite SVG ni ejecuta contenido activo.
- Fotos del maestro en tabla propia referida al mismo Producto; contenido binario diferido, no se carga en listas ni en JSON del formulario. Persisten con la transacción de DB, sin depender de archivos efímeros de Render ni activar Cloudinary. Las inclusiones comerciales anteriores y sus imágenes explícitas no se sobrescriben ni duplican automáticamente.
- Acceso a fotos por endpoint admin, con autenticación, organización/producto/imagen coincidentes, MIME comprobado, nosniff y caché privada. No son URLs públicas para publicar en canales.
- Búsqueda del maestro ampliada a código de proveedor, códigos de barras, marca, rubro y subrubro, con contexto tenant y sin duplicar filas. La tabla muestra clasificación/marca en forma compacta.

Persistencia y UX:
- Cinco tablas aditivas referidas a Producto: producto_datos_generales, producto_proveedor, producto_ubicacion, producto_codigo_barras y producto_imagen_maestra. No se agrega otro SKU ni se cambia el SELECT de Producto ni de su extensión anterior.
- Preparación independiente e idempotente, sin importar app.py ni iniciar scheduler. Conserva productos, fichas y relaciones existentes. El nuevo script también ejecuta la preparación anterior de ficha si es necesaria.
- Hasta preparar estas tablas, la ampliación no se muestra como disponible; el flujo anterior sigue funcionando. Detección de tabla y columnas antes de consultar.
- Ruta de alta/edición: ficha anterior, combo y datos nuevos con una única confirmación/commit. Un error de proveedor, códigos, fotos o permisos revierte también el producto/ficha creados. Fotos no se suben antes de confirmar. Cancelar no hace POST.
- La huella de concurrencia incluye la revisión y metadatos/relaciones nuevos, sin binarios. La importación anterior conserva la ampliación y rechaza una previsualización obsoleta; los nuevos campos relacionales/fotos no se agregan de manera improvisada al CSV anterior.
- Error conserva valores y listas; vuelve a seleccionar el producto editado aunque estuviera fuera de los primeros 100. Fotos nuevas rechazadas deben seleccionarse de nuevo, con aviso explícito; las guardadas se conservan según la selección revisada.
- Campos requeridos dentro de secciones plegadas se despliegan para mostrar la validación. Reconfirmación normal y prevención de guardado accidental con Enter se conservan.
- Sin cambio de main, flags, scheduler, conexiones externas, pedidos, cobros, liquidaciones ni stock real.

Verificación y límites:
- 83 pruebas funcionales aprobadas: 49 del maestro anterior, 17 nuevas de ficha completa (incluyendo casos parametrizados) y 17 del núcleo/inventario SaaS. Seis comprobaciones estáticas antiguas de inventario fuera del checkout reducido no se incluyen. Dos comprobaciones estáticas de modularidad/flush aprobadas aparte.
- Casos nuevos: preparación idempotente y proceso independiente sin app, unicidad por proveedor, ceros iniciales, aislamiento tenant, utilidad/costo/venta/vacío/cero, subrubro, permisos físicos, rechazo de retiro con saldo, imágenes válidas/falsas/grandes/repetidas/principal/reemplazo, endpoint autorizado/404, rollback integral, importación que conserva datos y detecta huella vieja, búsqueda por atributos/códigos.
- Prueba de DOM con HTML renderizado por Flask/Jinja y scripts reales: alta completa, ejemplo de margen, serialización, confirmación, cancelación, reapertura, proveedor duplicado y selección/cancelación de fotos aprobados. DataTransfer/dialog son adaptados en el entorno de DOM, no se declara prueba de browser.
- Sintaxis de ambos JS y compilación de módulos Python aprobadas.
- No se ejecuta el monolito ni PostgreSQL/Render. Chromium no pudo instalarse por descarga truncada; aceptación visual final y archivos reales quedan pendientes del UAT de staging. No se declaran aprobadas pruebas ajenas a este bloque que requieren archivos no disponibles del checkout parcial.

Deploy y próximo UAT (solo carga manual):
1. Desplegar el nuevo commit únicamente en integracion-saas-2026-09.
2. Shell de staging: python -m scripts.preparar_datos_productos --staging. Mantener BOOTSTRAP_BASE_DATOS_HABILITADO=false y MODO_LABORATORIO_DESCONECTADO=true.
3. Ctrl+F5 → Base de Datos → Productos → Nuevo producto. Revisar las secciones nuevas sin salir a otros procesos.
4. Crear un Simple ficticio UAT-FICHA-002: clasificación, proveedor existente/código 000-PRUEBA, sucursal/depósito seleccionados, utilidad 30 sobre costo, código de barras interno ficticio UAT-000002 y una o dos imágenes de prueba. Guardar/confirmar/reabrir, verificar todos los datos y foto principal.
5. Probar Cancelar cambios y proveedores con código igual en proveedores distintos; código igual en el mismo proveedor para otro SKU debe rechazarse íntegramente. Probar utilidad sobre venta 100 o superior y subrubro sin rubro: aviso, sin alta parcial.
6. Seguir limando el alta manual; no avanzar todavía a fabricación, precios operativos, importación real ni conexiones externas.

## 2026-10-20 · Alta manual por pasos en formularios emergentes

Pedido vigente: reemplazar los desplegables de la ficha por un recorrido APB, inspirado en DUX. La ampliación anterior de datos se conserva; las indicaciones de secciones plegables del bloque anterior quedan reemplazadas para Nuevo/Gestionar producto.

Resultado:
- Una sola pantalla del formulario emergente visible por vez: Datos básicos; Clasificación y proveedores; Stock y ubicaciones; Composición y utilidad; Imágenes y códigos; Envíos; Revisar y guardar.
- Anterior/Siguiente, indicador de paso y acceso a pasos ya visitados. Resumen final por sección con Editar. No hay acordeones en la ficha manual. La importación masiva mantiene su interfaz anterior.
- Datos, proveedores, ubicaciones, componentes y archivos seleccionados permanecen al avanzar o retroceder. Cancelar/cerrar no envía datos. Al abrir otra vez se carga la versión guardada.
- Solo el resumen ofrece Guardar producto; luego pide la confirmación normal. Enter en campos no dispara guardado. Un submit anticipado, incluso programático, valida y lleva al resumen; requiere otra acción explícita para confirmar. Protección ante doble envío conservada.
- Validación de campos en su paso; combo obligatorio y sin duplicados en Composición. Proveedores repetidos, códigos repetidos y porcentaje inválido llevan al paso correspondiente con aviso. La revisión/guardado revalida toda la ficha, aunque se vuelva con Editar. El servidor sigue siendo la autoridad de reglas e integridad.
- Se conserva el guardado atómico existente de maestro/combo/datos/fotos en el mismo POST; sin nueva entidad de producto, cálculo económico ni guardado parcial por paso. Sin tablas ni cambios de esquema nuevos en este bloque.
- El resumen construye texto con nodos de DOM; no interpreta nombres, códigos ni descripciones del usuario como HTML. Fotos con nombre y marca de principal; cantidades y códigos conservados.
- En instalaciones sin la ampliación preparada, se omiten los pasos vacíos de clasificación/imágenes y se conserva el recorrido básico.

Verificación:
- 66 pruebas del maestro y de datos generales aprobadas, incluyendo las rutas Flask/Jinja reales y guardado/rollback existentes.
- Sintaxis de ambos scripts aprobada.
- DOM con HTML real renderizado por Flask y scripts reales: navegación, campos obligatorios, avance sin POST, volver manteniendo proveedor/fotos, combo vacío rechazado, componente fraccionario con flechas de paso 1, utilidad sobre venta inválida, resumen y Editar, texto no interpretado como HTML, submit anticipado, cancelar y confirmar una sola vez aprobados. Conservadas las comprobaciones anteriores de datos, imágenes y serialización.
- DOM usa adaptadores de dialog/DataTransfer; no equivale a navegador real. No se pudo disponer de Chromium en este entorno; aceptación visual y funcionamiento nativo de los emergentes quedan pendientes en staging. No se ejecutó PostgreSQL/Render ni el monolito.

Siguiente UAT, exclusivamente alta manual:
1. Desplegar este commit de integracion-saas-2026-09; no requiere otra migración si ya se preparó la ampliación anterior. Mantener los flags de laboratorio.
2. Ctrl+F5 → Base de Datos → Productos → Nuevo producto. Recorrer los pasos, volver y comprobar que se mantienen los datos; revisar apariencia en el tamaño de pantalla habitual.
3. Seleccionar Combo y comprobar que Composición no deja avanzar sin componentes; usar el producto de prueba existente, con SKU propio para el combo.
4. En Revisar y guardar usar Editar, corregir y volver al resumen; comprobar Cancelar tanto en la ficha como en la confirmación. Guardar una única ficha de prueba y reabrir para verificar datos e imágenes.
5. No avanzar todavía a otros módulos: continuar sobre el resultado del alta manual. Main/producción, conexiones externas y stock real quedan fuera de este bloque.

## 2026-10-20 · Costo unitario, IVA y moneda en el alta manual

Pedido: permitir cargar precio de costo, porcentaje de IVA y elegir pesos o dólares. Se conserva el asistente de Nuevo/Gestionar producto, sin volver a desplegables ni abrir otro proceso.

Implementación:
- En Composición y utilidad: Precio de costo unitario (sin IVA), Moneda del costo Pesos (ARS)/Dólares (USD) e IVA (%). IVA editable con sugerencias 0/10,5/21/27; no se presume alícuota ni condición fiscal. Vacío y cero son estados distintos.
- Vista informativa de costo sin IVA, importe del IVA y costo con IVA en la moneda elegida. Si IVA está vacío no se calcula total gravado. Se admiten coma o punto decimal, sin separadores de miles; costo hasta dos decimales, IVA hasta seis, no negativos ni valores no finitos. IVA 0–100; monedas permitidas ARS/USD. No hay conversión automática ni nueva conexión de cotizaciones.
- El costo NO se duplica como otro importe en la ficha: referencia a CostoProductoVersion, con detalle unitario y creación mediante crear_version_costo(commit=False). Misma moneda, cantidad 1 y unidad de medida del maestro; importe sin IVA. El porcentaje fiscal se conserva en ProductoDatosGenerales, separado del costo neto.
- Carga general de la organización; no selecciona arbitrariamente una unidad de negocio. Cuando un Simple con costo no tiene perfil general, reutiliza crear_o_actualizar_perfil para crearlo del mismo tipo. No cambia ni reactiva perfiles existentes; no crea composiciones vacías para producción/combos.
- Nuevo importe o moneda generan versión preparatoria no vigente. Repetir el mismo costo no duplica versiones. Vaciarlo quita la referencia manual, conservando el historial. Un cliente anterior que no presenta estos campos conserva costo, IVA y moneda.
- No modifica una versión vigente ni activa/publica precios, impuesto de una regla económica o márgenes. Producción/combo conservan el cálculo de composición como fuente final; la carga manual no se hace pasar por costo calculado. USD no se consume como ARS en los motores existentes.
- Guardado con la ficha, relaciones y fotos en una sola transacción. Error posterior a crear el borrador revierte también Producto, ficha, perfil, versión y detalle. Lectura con organización/producto/ámbito general/tipo manual coincidentes. Huella incluye referencia, importe, moneda y estado cargados; edición obsoleta rechazada.
- Los nuevos campos se conservan al avanzar/volver, aparecen en el resumen, se reabren desde la base y mantienen los errores con los valores cargados. No se agregan al CSV anterior sin un diseño de importación específico.

Preparación:
- Tres columnas aditivas en producto_datos_generales: costo_carga_id (FK al historial existente), moneda_costo (ARS/USD) e iva_pct. Sin otro maestro ni tabla de importes paralela.
- El mismo script preparar_datos_productos reconoce el esquema anterior y agrega solo esas columnas faltantes, con validación previa de tablas y columnas de Costos. Es idempotente, conserva el contenido anterior y rechaza esquemas desconocidos. No importa app.py ni arranca scheduler. Hasta preparar se mantiene la guardia que evita consultar columnas ausentes.
- Se mantienen main, flags, producción, existencias, ventas, cobros y conexiones externas fuera del cambio.

Validación:
- 85 pruebas del maestro y datos generales aprobadas. Casos nuevos: historial reutilizado/no duplicado, USD/ARS sin conversión, IVA separado, vacío/cero, límites y formatos inválidos, versiones vigentes conservadas, clientes previos, aislamiento de organización, huella, ruta Flask de guardado/reapertura y rollback completo posterior a crear el costo.
- Migración del esquema anterior con contenido e idempotencia comprobadas en SQLite; proceso separado sin importar app comprobado. Sintaxis JS y compilación Python aprobadas.
- DOM con HTML real Flask y scripts reales: campos, validación por paso, costo inválido, IVA inválido, moneda en el ejemplo, conservación al volver/resumen y guardado con confirmación comprobados. Usa adaptadores de dialog/DataTransfer; no equivale a prueba visual en navegador.
- Falta ejecutar preparación en PostgreSQL/Render y aceptar visual en staging; no se afirma desplegado ni aplicado a producción.

UAT inmediato (seguir solo carga manual):
1. Deploy del commit de integracion-saas-2026-09.
2. Shell de staging: python -m scripts.preparar_datos_productos --staging. Mantener BOOTSTRAP_BASE_DATOS_HABILITADO=false y MODO_LABORATORIO_DESCONECTADO=true.
3. Ctrl+F5 → Base de Datos → Productos → Nuevo/Gestionar → Composición y utilidad.
4. Usar ficha ficticia: costo sin IVA 1000, IVA 21, ARS. La vista debe mostrar IVA 210 y total con IVA 1210; volver/revisar/cancelar y comprobar que no se guardó nada.
5. Guardar y reabrir: deben conservarse 1000/21/ARS. Probar otra ficha ficticia en USD con 12,34 e IVA 10,5; verificar moneda y valores, sin activar costos ni publicar.


## 2026-10-20 · Descripción opcional e independiente del nombre

- Corrección solicitada al revisar el primer paso del asistente: Nombre identifica al producto; Descripción agrega detalles y es opcional. Se elimina la copia automática del nombre a una descripción vacía en la normalización común de carga manual y lotes.
- Etiqueta Descripción (opcional), con ayuda para completar detalles/características o dejar vacía. Alta, edición y reapertura conservan vacío; cambiar el nombre no rellena ni modifica la descripción. Se permite borrar una descripción sin borrar el nombre.
- Producto.descripcion conserva el mismo campo y puede guardar cadena vacía; no requiere modificación de esquema. No se agrega otro nombre/SKU ni otra descripción paralela.
- Textos anteriores conservados: no se borran masivamente coincidencias nombre/descripción porque pueden haber sido ingresadas expresamente. La compatibilidad inicial de productos antiguos sin ficha sigue usando su dato histórico como propuesta de nombre; esta corrección elimina la copia inversa nombre → descripción en fichas guardadas.
- 88 pruebas del maestro y datos generales aprobadas. Nuevos casos de alta/edición/reapertura independiente, borrado explícito, alta masiva sin descripción y ruta Flask real con nombre requerido y descripción vacía. Sin cambios de producción, conexiones o stock.
- UAT: desplegar el commit de integración y Ctrl+F5 → Base de Datos → Productos → Nuevo producto. Completar nombre y dejar Descripción vacía, guardar y reabrir; debe continuar vacía. Agregar detalles y luego editar solo el nombre: los detalles se conservan. Esta corrección no requiere Shell ni otra migración; la preparación del bloque previo de costo/IVA/moneda sigue siendo necesaria si todavía no se ejecutó.

## 2026-10-20 · La construcción del costo comienza al crear el producto

Decisión confirmada: un producto de producción comienza su ficha de fabricación en Nuevo producto. Composición de costo es otra entrada de mantenimiento de esa MISMA ficha; no es un paso externo obligatorio ni un segundo registro. El costo no se escribe a mano para producción o combos.

Implementación en el asistente:
- Simple conserva costo de compra sin IVA, moneda ARS/USD e IVA. Producción oculta/deshabilita el importe manual y ofrece la construcción desde fuentes existentes; Combo conserva sus componentes y también deshabilita el costo manual. El servidor rechaza un importe manual para ambos tipos, incluso si se elude el navegador. No se activan conexiones ni conversiones de moneda.
- En Composición y utilidad aparece la ficha de fabricación con secciones en pestañas: Insumos y materiales (cantidad y merma por unidad), Mano de obra (tarea/recurso/minutos), Máquinas (operación/equipo/minutos) e Indirectos (asignación porcentual/unidades mensuales).
- Se reutilizan InsumoProductivo, empleados/recursos laborales, máquinas y costos fijos productivos existentes. No se genera otra receta ni otra identidad de producto. Los insumos respetan los vínculos de habilitación del maestro ya existentes.
- Unidad de fabricación explícita General o unidad de negocio; se validan organización, unidad y recursos activos. Se edita solo el ámbito elegido y se conservan los otros. Borradores locales por unidad al cambiar el selector. Se preservan observaciones existentes aunque no se reescriban en esta UI.
- Calcular costo unitario realiza un POST autenticado/con CSRF de solo lectura sobre el formulario aún no guardado. Usa construir_detalles + preparar_detalles existentes, con precios/tarifas vigentes en ARS. No guarda el producto, perfil, líneas ni versión al simular.
- El botón muestra Calculando y luego resultado/aviso visible; desglose por material/operación/recurso y total unitario en ARS. No suma IVA a la base de fabricación ni utiliza USD como ARS. El IVA del producto y la utilidad siguen siendo atributos separados.
- Cambiar la receta invalida el resultado previo. Respuestas de una simulación anterior no se aplican si se cambia el formulario o se abre otro producto. El resumen final muestra los datos de fabricación y el estado del cálculo.
- El alta manual nueva de Producción exige al menos un insumo/operación/recurso. Si una fuente no tiene tarifa vigente, el cálculo informa el faltante; se puede guardar la composición como costo pendiente, sin crear un costo cero. El mensaje de guardado indica ese estado. Un costo pendiente no habilita un precio/publicación.

Persistencia y guardias:
- Reutiliza PerfilCosteoProducto y ProductoInsumoCosteo/ProductoOperacionCosteo/ProductoMaquinaCosteo/ProductoCostoFijoCosteo. Los servicios existentes admiten commit=False conservando commit=True como valor anterior para sus otras pantallas.
- Una única transacción guarda maestro, ampliación, fotos, perfil, composición y, cuando puede calcularse, CostoProductoVersion/Detalle tipo calculado, preparatorio y no vigente. No se activa automáticamente ni se cambia una versión vigente. Composición igual a la última versión no genera otra versión idéntica.
- Si se simuló, se contrasta la huella del desglose al guardar; cambios de tarifas piden recalcular y revierten íntegramente. Sin simulación previa el servidor calcula con las fuentes vigentes o informa pendiente, sin inventar importes.
- La huella del maestro incluye todas las composiciones de fabricación por unidad. Una modificación desde Composición de costo invalida un formulario anterior y evita pisarla silenciosamente. IDs de líneas ajenas, unidades o recursos de otro tenant, duplicados, inactivos y cantidades/tiempos inválidos son rechazados.
- Las líneas quitadas se eliminan solo del perfil seleccionado, sin borrar snapshots históricos. Una excepción posterior a crear el costo revierte también producto/perfil/líneas/versiones. Cancelar no envía el guardado.
- La referencia antigua de costo manual en una ficha no Simple se desvincula al guardar el nuevo formulario, conservando su historial; no se interpreta como costo de fabricación.
- Se reutilizan tablas desplegadas de Costos; no hay migración nueva. Guardias de esquema antes de mostrar la ficha: si faltan tablas/columnas, se informa que no está disponible y no se admite reemplazar fabricación por costo manual. La preparación anterior de costo/IVA/moneda sigue siendo necesaria si no se ejecutó.
- Inspección de esquema reutilizada dentro de la petición, sin caché persistente que impida ver una preparación posterior. Sin cambios de main, stock, pedidos, scheduler o conexiones externas.
- Dos ajustes del cálculo existente: un indirecto distribuido por unidad pide seleccionar unidad, en lugar de fallar con int(None); un detalle de combo sin descripción opcional usa el SKU como concepto, sin volver a copiar nombres a descripciones.

Verificación y límites:
- 106 pruebas del maestro/datos/fabricación aprobadas; 18 casos de fabricación incluyen las cuatro fuentes, merma, cálculo previo sin escrituras, CSRF, guardado/reapertura sin duplicados, rechazos/rollback, tarifas faltantes, cambio de fuente tras simular, ámbitos independientes, edición externa obsoleta y bloqueo de costo manual para producción/combo. Una prueba adicional del cálculo anterior de composición aprobada.
- DOM con HTML Flask y scripts reales: cambio de tipo, bloqueo del importe, cuatro pestañas, feedback de cálculo, resultado sin interpretar texto como HTML, invalidación, borradores por unidad, resumen, cancelación y reapertura comprobados. El DOM adapta dialog/DataTransfer y la respuesta de cálculo; la API real se prueba aparte con Flask/DB.
- Sintaxis JS y compilación Python aprobadas. No se declara QA visual en navegador real ni ejecución de PostgreSQL/Render; queda la aceptación de staging. No se ejecuta el monolito ni pruebas estáticas ajenas que dependen de archivos no disponibles.

UAT inmediato, continuar solo el alta manual:
1. Desplegar este commit únicamente en integracion-saas-2026-09. No requiere otra migración por este bloque.
2. Ctrl+F5 → Base de Datos → Productos → Nuevo producto → Tipo De producción → Composición y utilidad.
3. Elegir unidad de fabricación y cargar insumo/cantidad/merma, tarea/recurso/minutos y máquina/minutos de prueba. Agregar un indirecto si corresponde al caso. Usar las fuentes ya preparadas; no activar servicios externos.
4. Calcular costo unitario y revisar el desglose. Volver a un paso anterior conserva los datos; Cancelar no crea producto/receta. Si falta una tarifa, debe indicar costo pendiente y no mostrar cero como costo válido.
5. Guardar una ficha ficticia y reabrir: misma composición, costos calculados en el historial sin activación. Cambiar una cantidad y recalcular; observar resultado actualizado. Seguir ajustando el alta manual antes de avanzar a ventas/publicación reales.


## 2026-10-20 · Alta de fabricación según PLANILLA GENERAL; IVA final e IIBB como costo

Este bloque reemplaza el ingreso agregado de insumos/merma y tarifa por tarea descrito en el bloque anterior. Se continúa exclusivamente el alta manual de Productos.

Reglas confirmadas por Martín:
- Todos los precios de fuentes y costos son sin IVA. No se calcula merma en esta metodología.
- Los tiempos de Tareas son por un producto/una unidad, no por lote.
- Lista Proveedores.Unidad define la unidad de cada fuente; su tarifa ya corresponde a metro/unidad. No volver a dividir por bulto de compra.
- IVA (%) permanece editable y persistido por producto. Solo se suma al definir el precio final de venta/publicación; se retira la vista previa anterior de costo con IVA.
- IIBB (%) configurable por producto: costo fiscal para precio/rentabilidad, sin concepto separado de facturación. Vacío significa sin definir; cero es explícito. No se importa ni presupone 3,5% del archivo de referencia.

Interfaz y reutilización:
- Composición y utilidad → ficha de fabricación con Componentes, Tareas, Resumen y Otros costos.
- Cada pieza se carga/edita en una emergente individual: nombre, material, cantidad y medida en cm para fuentes cotizadas por metro; también consumo directo o rendimiento por placa/cartón/unidad. Se pueden repetir materiales en distintas piezas y se suman automáticamente sus consumos.
- Cada tarea tiene su emergente, nombre y segundos/minutos por unidad. Una única tarifa configurada de mano de obra del taller para el conjunto; no se elige arbitrariamente el primer empleado ni se genera otra nómina/promedio.
- Resumen automático de consumos por fuente y tiempo total. Calcular muestra progreso, desglose y resultado neto; no escribe producto/costo al simular. Máquinas e indirectos existentes siguen disponibles como Otros costos.
- Las medidas originales y segundos se guardan como metadatos de UN MISMO PerfilCosteoProducto; alimentan las líneas existentes de insumos y operaciones. No se crea otro producto, motor o costo paralelo.
- El motor compartido suma segundos antes de calcular mano de obra y genera la misma versión preparatoria desde Productos o Costos. No activa versiones ni precios.
- La huella comprueba si Costos modificó posteriormente las líneas. Si las medidas dejaron de representar la composición, se informa y se usan los consumos actuales, no datos obsoletos.
- Recetas anteriores sin medidas se muestran como Consumo previo, sin inventar largo de piezas. Una merma histórica se incorpora al consumo efectivo para no reducirlo silenciosamente al pasar al nuevo método sin merma. Varias tarifas anteriores exigen elegir/revisar la tarifa del taller.
- Se preservan separación por organización/unidad, transacción atómica, huella de edición, rechazo de fuentes ajenas/inactivas, costo pendiente ante tarifas faltantes, cancelación sin envío y defensa de confirmación explícita.

Referencia PP6040H auditada en PLANILLA GENERAL(2).xlsm:
- 7 piezas: 24×39,5 cm varillas; 4×35,5 cm laterales; 2×59 cm patas; 2×16,5 cm manijas; 2×3 cm bisagras; 4 tuercas y 2 bulones.
- Resultado: 10,99 m hierro, 1,48 m planchuela, 4 tuercas, 2 bulones. 13 tareas suman 1156 segundos = 19 min 16 s.
- No se importa ni cambia ningún producto real o precio desde esa planilla. El ensayo automatizado usa fuentes y tarifas ficticias.
- Límite pendiente: el motor existente guarda tarifas monetarias en centavos; la planilla tiene precios de fuente con más decimales. Se verifica igualdad de método/cantidades/tiempos, no igualdad exacta de centavos con los precios históricos del archivo.

Alcance fiscal de este commit:
- Captura, validación, reapertura y persistencia de IVA/IIBB en el maestro; IIBB admite seis decimales en [0,100).
- Formularios anteriores sin indicador del nuevo campo conservan IIBB ya guardado.
- PENDIENTE al construir precio final: conectar explícitamente estos parámetros con las reglas económicas de cada canal y su base de cálculo, deduplicando impuestos/cargos existentes. Este commit NO afirma que guardar IIBB ya lo aplique al precio ML ni altera reglas económicas vigentes. Se mantiene la regla insalvable de neto mínimo; no se habilitan publicaciones con costos o cargos faltantes.

Preparación y verificación:
- Tabla aditiva producto_despiece_costeo, asociada al perfil existente; columna nullable iibb_pct en producto_datos_generales. Guardias de esquema impiden usar la ampliación sin prepararla, sin consultar columnas inexistentes.
- Ejecutar SOLO en Shell de staging después de desplegar: python -m scripts.preparar_despiece_productos --staging. Incluye la preparación anterior de datos generales; es idempotente y conserva datos. Mantener BOOTSTRAP_BASE_DATOS_HABILITADO=false y MODO_LABORATORIO_DESCONECTADO=true.
- 122 pruebas del maestro/datos/fabricación/despiece aprobadas, más una prueba nueva del script ejecutado en proceso aislado sobre copia SQLite y rechazo de rama main. El conjunto suma 123 casos. Se comprueban agregación PP6040H, unidades/rendimiento, segundos, huella compartida, guardado/reapertura, no duplicación, cambios externos, preservación de IIBB, límites y rollback integral después de guardar las piezas.
- DOM con HTML Flask y scripts reales: emergentes individuales, cancelar sin agregar/guardar, materiales repetidos, cm/metro, tareas/segundos, resumen, feedback y confirmación, IVA/IIBB habilitados y costo neto. Respuesta de cálculo simulada en DOM; API probada separadamente con Flask/DB.
- Sintaxis JS y compilación Python aprobadas. No se declara QA visual de navegador real ni ejecución de PostgreSQL/Render; sigue pendiente la aceptación visual en staging.
- Sin cambios de main, stock, pedidos, scheduler o conexiones externas.

UAT siguiente, sin salir del alta manual:
1. Desplegar el commit en integración y ejecutar el comando de preparación anterior en staging.
2. Ctrl+F5 → Base de Datos → Productos → Nuevo producto → De producción → Composición y utilidad.
3. Cargar piezas/tareas de una ficha ficticia siguiendo el ejemplo PP6040H. Elegir tarifa del taller ya configurada; no inventar precios de fuentes faltantes.
4. Revisar consumos/tiempo, IVA elegido e IIBB que corresponda al caso. Calcular: costo neto o aviso claro de fuente pendiente; no costo con IVA.
5. Cancelar primero y comprobar que no se creó nada. Luego guardar ficha ficticia y reabrir: mismas piezas/tiempos/IVA/IIBB y versión preparatoria, sin activación.

## 2026-10-20 · Fabricación propia en lugar de seleccionar proveedor

- En Clasificación y proveedores, sección Origen y proveedores, se agrega la opción visible Fabricación propia junto a Agregar proveedor. No se crea a Fierro como proveedor ficticio.
- Se reutiliza el tipo De producción del maestro: si ya fue elegido en el primer paso, Fabricación propia aparece marcada automáticamente. Seleccionarla desde un producto Simple cambia el tipo a De producción mediante el mismo evento del selector, habilitando su ficha de fabricación y bloqueando costo manual. La ayuda lo explica antes de elegir.
- No exige proveedor ni código externo para elaboración propia. Proveedores existentes se conservan y pueden agregarse si el mismo producto también se compra terminado; no se mezclan con proveedores de sus materias primas.
- La opción no convierte combos ni elude las restricciones existentes del cambio de tipo. No se guarda otro indicador de origen que pueda contradecir el tipo; no requiere esquema adicional.
- Cancelar no guarda el cambio de tipo ni crea proveedor. La selección se recupera al reabrir a partir del maestro guardado.
- Pruebas: suite de datos generales y despiece aprobada; DOM Flask/scripts reales comprueba elección desde Simple, selección automática al reabrir producción, ausencia de proveedor artificial, ningún POST al seleccionar, sincronización al cambiar tipo y bloqueo para Combo. Sintaxis JS aprobada. Aceptación visual pendiente de staging.
- UAT: desplegar este commit de integración, Ctrl+F5 → Base de Datos → Productos → Nuevo → Clasificación y proveedores. Un De producción ya debe indicar Fabricación propia seleccionada; un Simple puede elegirla ahí y continuar con componentes/tareas. Cancelar y luego guardar/reabrir una ficha ficticia. Sin cambios en main o conexiones.
- Este ajuste no requiere otro comando de preparación; si todavía no se preparó el bloque anterior de despiece/IIBB, sigue pendiente python -m scripts.preparar_despiece_productos --staging en Shell de staging.

## 2026-10-20 · Importación de insumos con cantidad y precio por bulto

Decisión de Martín: importar de una vez los insumos de Lista Proveedores. La preparación contiene 33 insumos con precio; PS-CRUDO-5MM y PS-PLUS BLANCO-5MM quedan fuera por no tener precio ni consumo en productos activos. No se les asigna cero. Las cantidades de bulto no informadas quedan vacías para completarlas manualmente; medidas como 1,8*2,6 se conservan separadas y no se interpretan como cantidad.

Este bloque cierra el pendiente anterior del importador que ignoraba Bulto. Se amplía el importador existente; no se crea otro maestro ni otra identidad de insumo.

Contrato de cotización, todo sin IVA:
- Cantidad por bulto: metros/unidades de la misma unidad de medida del insumo, positiva y hasta seis decimales; puede quedar sin definir.
- Precio unitario: tarifa por metro/unidad que utiliza la fabricación. Un precio ya normalizado NO se divide nuevamente al informar el bulto.
- Precio por bulto: importe del paquete/barra/caja cotizado por el proveedor. La cotización bulto requiere cantidad y precio del bulto, y calcula una vez precio unitario = importe / cantidad.
- Cotización explícita unitario o bulto. Un archivo antiguo con precio unitario sigue siendo unitario; si solo informa precio por bulto se interpreta esa base. Si informa ambos se contrasta su coherencia con la base elegida; no se ignora una discrepancia.
- Ejemplo ficticio: $600 netos por barra de 6 metros guarda $100 netos por metro y conserva $600 como precio del bulto. $100 por bulto de 6 metros guarda $16,67 por metro, manteniendo el importe real de $100 y sin reconstruir $100,02 como si fuera lo cotizado.
- Los costos productivos siguen leyendo la MISMA InsumoPrecioVersion, en centavos. Se mantiene el límite de precisión del motor existente; el precio original por bulto se conserva para no perderlo por redondeo unitario.
- IVA no se incorpora a estas fuentes. IIBB y cálculo final de precio de publicación mantienen el alcance/pending definido en el maestro; este bloque no activa reglas económicas ni publicaciones.

Implementación:
- InsumoPresentacionCompra: cantidad/presentación opcional asociada al insumo existente. InsumoPrecioBultoVersion: referencia 1:1 a la versión histórica de precio existente, con cantidad, importe del bulto y base de cotización de ese momento. No duplica un catálogo/SKU ni reemplaza versiones de costos.
- Las dos tablas son aditivas. Se guardan en la misma transacción del alta o actualización del insumo y su precio. Los servicios de versionado admiten commit=False para este recorrido, manteniendo el comportamiento anterior por defecto.
- Lectura protegida antes de preparar esquema: no agrega columnas a consultas ORM de tablas desplegadas y no produce UndefinedColumn. Una importación con datos de bulto sin esquema se rechaza antes de aplicar la primera fila.
- CSV/Excel anteriores sin columnas nuevas siguen admitidos. Columnas vacías/no mapeadas conservan cantidad y medidas ya guardadas; no significan bulto de una unidad ni borrado. El precio faltante sigue rechazado salvo que se proporcione cotización por bulto completa. Cero es un importe explícito, no un reemplazo del faltante.
- Se rechazan cantidad cero/negativa, NaN/infinito, exceso de precisión/rango, medidas en cantidad, precios contradictorios y cambios de unidad de un insumo existente que requieren revisión. Organización y unidad se validan antes de escribir.
- Plantilla, mapeo automático, previsualización y exportación incorporan Cantidad por bulto, Medidas en origen, Cotización y Precio por bulto. La columna Revisión del archivo preparado queda sin importar.
- La pantalla existente Fuentes de costo → Insumos y precios permite crear/gestionar ambos tipos de cotización, solicita solo el importe correspondiente y muestra feedback del costo unitario. Listado e historial distinguen bulto cotizado de bulto calculado desde tarifa unitaria.
- El lote conserva la revalidación y el popup de confirmación existentes, sin escribir frases. La aplicación por filas mantiene el comportamiento previo del importador; no se afirma transacción global de todo el lote.
- El importador conserva Proveedor como referencia de texto, según su contrato existente; no crea personas/proveedores ni inventa vínculos al maestro por nombre. La identidad y los códigos del proveedor requieren seguir el esquema de vínculos del maestro ya definido. No se resuelven equivalencias solo por nombres.

Validación:
- Conjunto de maestro/datos/fabricación/despiece/importador/bultos: 160 pruebas aprobadas; guardia adicional de esquema antes de la primera fila verificada en la suite focalizada de 38 casos, que también pasa (161 casos en total cubiertos).
- Se ejecutan los dos recorridos reales de administración de insumos y servicios ORM sobre SQLite aislado, cargando sus acciones sin los imports operativos ajenos no disponibles. Se comprueban precios unitarios sin división, bulto convertido una vez, origen real/historial, decimales, vacíos/formularios anteriores, inmutabilidad de unidad, límites, tenant, rollback integral y esquema ausente.
- Script independiente probado sobre copia SQLite: preparación idempotente, conservación de datos y rechazo de main. No se ejecuta el monolito ni conexiones.
- Archivo preparado de 33 insumos: lector, mapeo, previsualización y aplicación completos en SQLite aislado, con comprobación de códigos, unidades, precios y cantidades. Esto no acredita datos importados en Render/staging ni examina una copia que Martín haya completado fuera del chat.
- HTML Flask y scripts reales verificados con DOM: cotización unitario/bulto, campos habilitados y requeridos correctos, importe inactivo no enviado, feedback $600/6=$100 y reapertura de cantidad/base guardadas. Sintaxis JS y compilación Python aprobadas. Aceptación visual en navegador real y PostgreSQL/Render pendientes.

UAT e importación:
1. Desplegar el commit solo en integracion-saas-2026-09. Mantener BOOTSTRAP_BASE_DATOS_HABILITADO=false y MODO_LABORATORIO_DESCONECTADO=true.
2. En Shell del servicio STAGING ejecutar: python -m scripts.preparar_bultos_insumos --staging. Crea exclusivamente las dos tablas de presentación; no conecta canales ni modifica precios/insumos existentes.
3. Ctrl+F5 → /admin/comercial/importaciones/fuentes/insumos. Usar el archivo de 33 insumos ya completado por Martín, no reemplazar su copia con otra vacía.
4. Para el archivo preparado los importes son unitarios: no mapearlos como precio por bulto. Operación Crear y actualizar → Leer archivo → verificar Cantidad por bulto y Medidas en origen → Validar y previsualizar. Los dos sin precio no forman parte del lote.
5. Revisar 33 filas, sin rechazos inesperados, los importes por unidad/bulto y los códigos existentes. Confirmar importación y aceptar el popup. No volver a confirmar un lote completado.
6. Fuentes de costo → Insumos y precios → Ver insumos cargados: verificar cantidades y precios por unidad/bulto, gestionar una ficha de ensayo y revisar historial. Para futuras listas cotizadas por bulto usar la plantilla nueva y Cotización=bulto con cantidad y precio del bulto.


## 2026-10-20 — Presentación de importaciones de fuentes de costo
- Base oficial: `61eb0ce011762918fe72688e5949339878093b78`, rama `integracion-saas-2026-09`.
- Evidencia del usuario: pantalla de importación completada de `insumos_lista_proveedores.xlsx`, 33 creados, 0 actualizados y 0 rechazados. No repetir esta importación para revisar el diseño.
- Vista previa de insumos agrupada en seis columnas: fila, insumo (nombre/código/tipo), proveedor, presentación (cotización/cantidad/precio por bulto/medidas), costo por unidad y resultado con motivo del rechazo. Se mantienen visibles los diez campos originales; no cambia el cálculo ni el contenido confirmable del lote.
- Estilos exclusivos para esta pantalla: tipografía legible, resumen de cantidades, encabezados fijos con desplazamiento interno, precios destacados y acciones alineadas; ayuda de cotización plegada y oculta al completar. Historial con etiquetas de estado legibles; pantalla final identifica el archivo.
- Confirmación, revalidación y bloqueo de lotes completados conservados. No hay migraciones, cambios de modelos, conexiones externas ni modificaciones de producción.
- Validación: 23 pruebas aprobadas (`test_importacion_fuentes_presentacion.py` y `test_importacion_fuentes_costeo.py`). Render Jinja con variables estrictas, conservación de campos/precios, escape de texto, otras cinco fuentes y ausencia de acción confirmar en lotes completados. Sin inspección visual en navegador real; pendiente UAT visual en staging.
- UAT siguiente: desplegar este commit en staging y Ctrl+F5; revisar resultado e historial existentes. Para revisar una vista previa nueva, usar Solo validar, comprobar datos unitarios/bulto, errores y desplazamiento, sin confirmar ni duplicar los 33 insumos.


## 2026-10-20 — CUIT/ARCA en altas y teléfono de contacto del proveedor
- Base oficial: `a99d0be3111ad42940adc0601f01600dba966b68`, rama integración. Solicitud: consultar CUIT para autocompletar altas de clientes y proveedores, más teléfono propio de la persona de contacto del proveedor.
- Una sola consulta/adaptador ARCA compartida por ambos maestros. Reutiliza EntidadFiscal/ConfiguracionFiscal y los controles de administrador/tenant de los blueprints. Consulta POST con CSRF global, CUIT con dígito verificador, revisión y aplicación explícita antes de guardar. Por defecto conserva lo escrito; opción de reemplazo. Cambiar CUIT, descartar o cancelar invalida respuestas anteriores. No guarda ni activa entidades al consultar.
- Datos consultables: razón social/nombre, domicilio fiscal, localidad, provincia y código postal. Email, teléfono y contacto siguen manuales; no se presume condición IVA ni se modifica facturación, pedidos o domicilios de envío.
- Proveedores: teléfono general y teléfono de la persona de contacto separados en alta, edición y detalle; guardado atómico con el proveedor, incluido rollback. Clientes: extensión uno a uno para domicilio/código postal y consulta en Ver datos; el alta sigue creando desactivado.
- Preparación aditiva de dos tablas complementarias: `python -m scripts.preparar_maestros_contacto --staging`, solo servicio/URL/branch de staging desconectado, idempotente. Si falta, las pantallas no hacen SELECT de columnas inexistentes: campos nuevos deshabilitados con aviso; altas antiguas disponibles; servidor rechaza guardar datos nuevos sin soporte.
- Consulta real NO activada: se respeta MODO_LABORATORIO_DESCONECTADO y frontera central ARCA. Adaptador consume loginTicketResponse WSAA vigente del servicio de constancia desde token_env existente; obtención y renovación automática de ticket/certificado pendientes antes de operación productiva desatendida. Selección de entidad explícita y aislada por organización. Documentado en `docs/CONSULTA_ARCA_MAESTROS.md`; sin secretos en código/chat.
- Validación: 77 pruebas aprobadas (ARCA, roles/tenant con blueprint real aislado del monolito, contacto/domicilio con SQLite, alta CRM, transacciones, render de ambas pantallas y regresiones importaciones). Interacciones DOM de ambas altas aprobadas: consulta/revisión/aplicación/rechazo, preservación de datos manuales y teléfono general, descarte/reset y respuesta tardía. Sin consulta real ni QA visual en navegador real.
- UAT siguiente: deploy staging, ejecutar preparación, Ctrl+F5; crear/editar/cancelar teléfono de contacto con datos UAT; crear cliente UAT y verificar domicilio. Consultar CUIT en ambas altas debe avisar bloqueo de entorno y conservar datos. Mantener flags false/true vigentes; no reimportar los 33 insumos ni tocar producción.


## 2026-10-20 — Buscar materiales del componente en los maestros existentes
- Base oficial: `e7878092811ed9121a0d0395ca084b5146705792`. Continuación solicitada en el emergente Componente del producto del alta manual de Productos.
- Material/insumo con búsqueda por SKU vinculado, código del insumo, código de proveedor, nombre y proveedor. Identificador exacto tiene prioridad; códigos repetidos conservan resultados distintos con proveedor y unidad visibles. Los alias SKU/código proveedor se obtienen por enlaces ProductoFichaMaestra.insumo_id y ProductoProveedor, nunca por coincidencia de texto.
- Autocompletar en Nombre de la pieza sobre esos mismos insumos; elegir sugerencia vincula el material. El nombre sigue editable/libre (p.ej. Varillas del emparrillado). Elegir otro material conserva un nombre de pieza propio. El material requiere elegir un resultado; texto libre o búsqueda sin selección no se guarda como identidad.
- Reutiliza InsumoProductivo y su costo/unidad vigentes; proveedor de referencia proviene del historial existente. Fuente sin SKU conserva su código y nombre, no genera un SKU nuevo. Datos restringidos al tenant; sugerencias filtran fuentes activas y unidad de fabricación como antes. Sin migración, nueva API, creación de productos/fuentes ni cambio de fórmulas.
- Selector con teclado, mensajes de coincidencias, límite visible de 8 resultados para afinar búsqueda, nombres/códigos mediante textContent y selección por ID. Conserva edición, cancelación y consumo de piezas/cm/metro/rendimiento.
- Validación consolidada: 217 pruebas aprobadas (maestro/productos/datos/fabricación/despiece/bultos/importaciones y CUIT/contactos/CRM). DOM del selector aprobado para SKU, nombre, código repetido entre proveedores, activos/unidades, nombre libre, material obligatorio, teclado, consumo, edición y cancelar; DOM previo de despiece también aprobado. Sin inspección visual en navegador real.
- UAT siguiente: desplegar último commit de integración; en Base de Datos / Productos → Nuevo producto → De producción → Composición y utilidad → Componentes → Agregar componente, buscar un insumo importado por código/nombre y verificar proveedor/unidad. Probar nombre propio y cancelar; después agregar y revisar consumo. SKU solo aparecerá si el vínculo real está cargado. No repetir importación de los 33 insumos.
- El último commit incluye además el bloque anterior ARCA/contactos: ejecutar una vez `python -m scripts.preparar_maestros_contacto --staging` para habilitar los nuevos campos de clientes/proveedores. Mantener laboratorio desconectado; consulta ARCA real pendiente de autorización y renovación WSAA.


## 2026-10-20 — Regresión de búsqueda por código 21572 y alcance de unidad
- Base oficial: `4b39b89fd51341ce966b5068c09d3c4fb93b7871`. Captura de usuario: 21572 sin coincidencias en el editor de componentes.
- Inspección de solo lectura: el archivo de importación conserva 21572 como código del insumo. El importador asigna los insumos a la unidad activa; el alta de fabricación abría General sin unidad y el filtro excluía esas fuentes. No hubo consulta directa a la base de staging; causa reproducida con importación y DB aislada.
- Alta sin receta previa toma la unidad activa de sesión si está activa y pertenece al tenant. Si no existe selección válida y solo hay una unidad activa, usa esa; con varias sin selección queda General. Las recetas existentes y reintentos con unidad explícita, incluida General, conservan su elección.
- Etiqueta Unidad de fabricación y contexto visible Buscando en en el editor. Ante ausencia de resultados, distingue coincidencias activas de otras unidades e insumos inactivos. Informa dónde buscar sin habilitar recursos de otra unidad, modificar la composición ni cambiar la unidad automáticamente desde un resultado.
- Validación: regresión 21572 mediante importador real aislado; se conserva el código/unidad y el servidor sigue rechazando su uso desde General, permitiéndolo en la unidad correcta. Pruebas de defaults con unidad actual, segunda unidad, ajena e inactiva. Verificaciones DOM: nueva ficha encuentra 21572 en unidad inicial; General muestra aviso explicativo; receta existente General permanece igual. Regresiones DOM del selector y del despiece aprobadas; sin QA visual en navegador real.
- UAT: desplegar este commit en staging, Ctrl+F5 y abrir alta nueva → fabricación propia → componentes. Verificar unidad y buscar 21572. Para una ficha ya abierta/guardada en General, elegir la unidad donde se importó (Ensayo UAT en la evidencia previa). No reimportar ni ejecutar migración/Shell por este ajuste.


## 2026-10-20 — Guardar y agregar otra en la carga de fabricación
- Base oficial: `377632d3a57b6e654cf894276e7be2b44eab46b2`. Pedido desde el emergente Tarea de fabricación.
- Se agrega Guardar y agregar otra en Tareas y Guardar y agregar otro en Componentes, junto al botón existente que agrega/cierra. Ambos usan la misma validación y registro en el borrador de la ficha; no guardan el producto en la base ni disparan red.
- Al continuar se confirma la incorporación en el cuadro, se limpian los campos y se enfoca el siguiente ingreso. Tareas conserva la elección segundos/minutos; Componentes vuelve a material sin seleccionar y cantidad 1 para evitar arrastrar un material o una medida anteriores. Al editar, aplica a la fila existente y luego inicia una nueva, sin duplicarla.
- Respeta el máximo existente de 100 filas, también al encadenar altas; al alcanzarlo informa y bloquea nuevas altas, conservando Cancelar. Los botones recuperan su estado al volver a editar/quitar filas.
- Validación: comprobaciones DOM de carga continua en tareas/piezas, validación vacía, agregar/cerrar, editar sin duplicar, foco, reset, unidad de tiempo, cancelar y límite 100 aprobadas; regresiones DOM de selector y despiece aprobadas; 17 pruebas Python de despiece aprobadas. Sin QA visual en navegador real.
- UAT: deploy staging, Ctrl+F5; en Tareas cargar dos tareas con Guardar y agregar otra y terminar con Agregar tarea. Comprobar listado, tiempos y edición. Las filas se persisten junto con Guardar producto. No requiere Shell/migración.


## 2026-10-20 — Ver producto: ficha integral de consulta del maestro
- Base oficial: `fc98dc7e133d917cf0f9a1ba94c5835bdb5c031c`. Pedido: consultar el producto cargado desde Productos, usando DUX solo como referencia informativa y conservando el formato de Fierro.
- Botón Ver producto junto a Gestionar en Base de Datos / Productos. Abre un emergente de consulta con pestañas, encabezado compacto, desplazamiento interno, cierre y restitución del foco al listado. No sustituye el asistente de edición.
- Reutiliza la lectura del maestro y sus composiciones existentes. Datos generales, descripción independiente, clasificación, usos, No stockeable, permitir stock negativo, logística, IVA, IIBB y utilidad; proveedores con código externo/contactos; sucursales/depósitos y existencias internas; imágenes y códigos de barras. Mantiene el tipo real: fabricación para producción, composición para combo y ficha general para simple.
- Fabricación muestra por unidad las piezas y medidas guardadas, consumos actuales, tareas/tiempos, operaciones, máquinas y costos indirectos. Advierte si el despiece anterior quedó desactualizado respecto de Costos. Historial de costos con detalle, moneda, unidad, versión y vigencia; no recalcula ni activa versiones preparatorias.
- Lista precios y vínculos/observaciones de canales ya almacenados por ID y organización. Distingue datos guardados de información en vivo; no consulta APIs ni activa conexiones. Módulos opcionales aún no preparados muestran su estado sin crear tablas. Cero costos o cantidades se distinguen de datos ausentes; fechas en hora argentina.
- Acceso GET autenticado con rol admin y aislamiento de organización tanto del producto como de listas/cuentas vinculadas; HTML escapado y respuesta no-store. Sin formularios de escritura en la ficha. Maneja carga, error, sesión vencida y respuesta tardía después de cerrar.
- Validación: 131 pruebas del maestro, datos generales, fabricación, despiece, selector y consulta aprobadas; incluye SQL sin escrituras durante la consulta, producción con costo preparatorio conservado, combo con identidad propia, privacidad tenant, rol, escape HTML, formatos y módulos opcionales. DOM con HTML real: siete pestañas, teclado, cierre/foco, errores y respuesta tardía; solo GET y cero envíos de formulario. Sintaxis JS aprobada. Pendiente QA visual en navegador real.
- UAT siguiente: deploy en staging y Ctrl+F5. Base de Datos / Productos → PP6040H → Ver producto. Revisar Datos generales; Fabricación (piezas, insumos, tareas); Costos y precios (expandir versión guardada); otras pestañas según datos existentes. Cerrar y comprobar que conserva la posición. Comparar con Gestionar sin guardar cambios. Sin Shell ni migración; producción fuera de alcance.


## 2026-10-20 — Acciones de producto con iconos
- Base oficial: `8a387e9c4f888de3d983939a1e11730a7c222f96`. Pedido: ojo para consultar y engranaje para gestionar.
- Sustituye las dos etiquetas visibles del listado por SVG de ojo y engranaje, con tamaño/color/alineación uniformes, área de 40 × 40 px y foco visible. Conserva title y nombre accesible con SKU; respeta Gestionar deshabilitado cuando corresponda. Sin dependencias ni recursos externos.
- Conserva los mismos botones, selectores y acciones de consulta/edición. Sin cambios de datos, rutas, permisos ni formularios. UAT: deploy staging, Ctrl+F5, Base de Datos / Productos; verificar ojo abre ficha y engranaje abre Gestionar; pasar el mouse muestra la acción. Sin Shell/migración; producción fuera de alcance.
- Validación: HTML renderizado con ambos SVG, nombres accesibles por SKU, títulos y botones type=button; regresión DOM de consulta, pestañas, cierre/foco y errores aprobada. Pendiente revisión visual en navegador real de staging.


## 2026-10-20 — Ojo y engranaje compartidos para consulta y gestión
- Base oficial: `dd6310fa765dd9a693c14d5b681d51592f8e2f22`. Usuario aprobó la presentación del maestro en captura image(20261020-223331).png y pidió extenderla a acciones equivalentes del sistema.
- Inventario de las 110 plantillas y 22 scripts oficiales: se identifican 52 controles de consulta/edición/gestión en 18 pantallas, más los botones de edición creados dinámicamente. Abarca Productos, Comercial, fuentes de costos, proveedores/Compras, Clientes, Pagos y vencimientos, Estructura, Inventario, Producción, Facturación/lotes fiscales, Rentabilidad ML, consulta de pedidos/histórico y archivos adjuntos.
- Componente común `acciones_iconos.js/css`, cargado desde base y también en la página autónoma de impresión que enlaza al original. SVG internos de ojo/engranaje, área uniforme 40×40 px, colores Fierro, foco visible, title y nombre accesible; los textos originales se conservan ocultos visualmente. Sin JS permanecen las etiquetas de texto. No hay biblioteca ni recurso externo nuevo.
- Los controles se marcan explícitamente mediante data-fierro-icon, sin convertir textos por coincidencia global. Se conservan los nodos de botones/enlaces/summary, sus eventos, destinos, formularios, permisos, estados disabled y confirmaciones. El observador incluye filas/emergentes posteriores e ignora nodos desconectados. Se integra con la conversión existente de Proveedores/costos a modal y con edición dinámica de componentes, piezas y tareas.
- Navegación principal, títulos de secciones, controles de guardar/cancelar y operaciones con otro significado mantienen su presentación. En el listado de pedidos el ojo corresponde a la consulta admin; Carga/Despacho conservan Continuar proceso. No se modifican estados de pedidos ni scheduler; producción fuera de alcance.
- Validación: contratos de enlaces, métodos, nombres/valores, onclick/onsubmit y hooks comparados contra el padre en las 19 plantillas modificadas (incluye base): intactos. Sintaxis Jinja de las 110 plantillas y sintaxis de los cuatro JS modificados aprobadas. DOM: accesibilidad, enlaces/target, disabled, listeners, envío original del formulario, apertura nativa de details, conversión real de proveedor a modal y filas dinámicas sin duplicar. Regresiones DOM de ficha y carga continua aprobadas, incluyendo ambos recursos comunes.
- Suite Python: 131 pruebas de maestro/fabricación/consulta aprobadas y cuatro de Compras aprobadas. Se actualiza el fixture de proveedor de este último test para resolver el include ARCA y contactos existentes (el padre fallaba por loader ausente), y se verifican acciones con atributos semánticos en vez de exigir summary sin atributos.
- UAT: desplegar este commit en integración/staging y Ctrl+F5. Revisar ojo/engranaje en Productos, Proveedores, Clientes, Comercial/Costos, Inventario, Producción y Administración/Pagos y vencimientos. Pasar el mouse/enfocar, abrir y cerrar; en un borrador de producto probar editar pieza/tarea y cancelar. Validación visual real pendiente de esta UAT. Sin Shell/migración, sin nuevas conexiones externas.


## 2026-10-20 — Filas alternadas en todas las tablas de pantalla
- Base oficial: `ee6834117b3e251ed449f72cc3e55de20037a832`. Captura image(20261020-224933).png inspeccionada localmente. Usuario solicita alternancia de filas para facilitar la lectura en todo el sistema.
- Hoja común `static/tablas.css` desde base y las dos pantallas autónomas de impresión con tablas. Fondo blanco con sombreado gris azulado en filas pares. Se usa una capa de color sobre las celdas, conservando los fondos de estados/alertas y los encabezados. Se unifican los sombreados locales previos de importación y ficha de producto.
- Selector de filas pares cuenta las filas visibles: excluye hidden, display:none y filas auxiliares de edición de Compras. Funciona sobre cada tbody, incluidos emergentes y tablas incorporadas después. No agrega JavaScript ni modifica filas o datos.
- Reglas limitadas a media screen; las etiquetas y documentos impresos conservan su presentación. Validación de CSSOM y sintaxis Jinja aprobada. No hay navegador real disponible para certificar contraste/paridad visual; pendiente UAT en staging con filtros y estados.

## 2026-10-20 — Duplicar producto desde el engranaje
- El engranaje de Productos abre un menú compacto con Editar producto y Duplicar producto. Duplicar prepara un borrador en el mismo asistente de alta para revisar y adaptar datos antes de guardar; cancelar no crea registros.
- Conserva nombre/descripción independientes, clasificación, proveedores seleccionados, usos, opciones de stock, ubicaciones, impuestos, utilidad, logística, costo manual editable de simples y composición de combos/fabricación. La composición que se guarda corresponde a la unidad elegida en el asistente; no se copian silenciosamente perfiles de otras unidades. La fabricación vuelve a usar el cálculo y la validación actuales.
- SKU empieza vacío y editable; rechaza reutilizar el SKU de origen en el primer paso. Códigos de barras y códigos externos de proveedor se vacían porque deben identificar al nuevo producto; conserva los proveedores para completar códigos propios. El vínculo único como insumo y los IDs de ficha/perfil/líneas se limpian. El servidor conserva sus validaciones de SKU, identidad, organización, habilitaciones y composición.
- Las fotos se leen mediante GET autenticado exclusivamente de las rutas internas del maestro y se incorporan como archivos nuevos, editables y con su principal conservada. No hay URLs externas ni conexiones de canal. Se informa la preparación; una foto inválida, sesión vencida o error impide abrir una copia incompleta. Cancelación, timeout e intentos tardíos se invalidan. Tras un rechazo de guardado se aplica el aviso existente para volver a seleccionar fotos nuevas.
- Reutiliza crear_producto y la transacción completa del alta; no se agrega endpoint de escritura, migración ni lógica paralela de guardado. No copia stock, reservas, pedidos, publicaciones, precios históricos ni vigencias: el costo manual o calculado genera su versión nueva preparatoria según las reglas existentes. No modifica el original.
- Validación: 137 pruebas Python aprobadas entre maestro, despiece, fabricación, datos generales, consulta, selector, Compras y dos regresiones nuevas de duplicación. Estas últimas prueban fotos/costo manual nuevos y producción con despiece propio modificado, preservando la huella original. El test de listado vacío se ajusta a verificar ausencia de acciones por fila, ya que el menú oculto ahora contiene el título Gestionar.
- DOM sobre HTML real: menú editar/duplicar; producción con siete piezas y trece tareas; simple con moneda/costo; combo con cantidad; limpieza de identidades/códigos; conservación de fuente; copia de foto; SKU distinto; cancelar; error de foto; respuesta tardía; revisión y popup antes del alta normal. Regresiones de consulta y carga continua aprobadas. Sintaxis JS aprobada. QA visual real pendiente de staging.
- UAT conjunta: deploy de este commit, Ctrl+F5. Base de Datos / Productos → engranaje de un producto → Duplicar producto → ingresar SKU nuevo → revisar/adaptar datos → revisión final → Guardar producto y confirmar. Probar primero cancelar; después guardar una copia UAT y comparar ambos con el ojo. Revisar alternancia también en otras tablas, filtros y filas de alerta. Sin Shell/migración; producción fuera de alcance.


## 2026-10-20 — Importación completa de fabricación desde Planilla General
- Base oficial: `5143337b1f0fd7be6cffc6f2c5b366739f81c67f`. Pedido autorizado: trasladar los productos existentes de fabricación propia al maestro, sin incluir los llaveros. No reemplaza el importador básico ni agrega otro motor de costos.
- Base de Datos / Productos → Importar productos → Importar fabricación propia. Lee XLSX/XLSM (Productos, Componentes, Tareas y Resumen Producto); no ejecuta fórmulas/VBA ni copia totales calculados. Archivo máximo 2 MB, hasta 500 productos, límites de expansión ZIP y filas/columnas.
- Conserva íntegro todo SKU existente de la organización, incluida PP6040H; excluye L-MDF-001 a L-MDF-005. Para los nuevos usa De producción, unidad de medida unidad y los usos revisados en el formulario. Sin stock negativo por defecto, sin crear existencias ni habilitar envíos por datos ausentes. No importa imágenes, ubicaciones ni códigos de proveedor como si fueran SKU nuevos.
- Reutiliza los insumos ya cargados y sus alias de SKU/código de proveedor; no duplica insumos/proveedores, no cambia precios ni tarifas. Código ambiguo/inexistente, recurso ajeno/inactivo, unidad incorrecta, costos incompletos, SKU repetido y datos inválidos bloquean el lote completo. Selección explícita de unidad, mano de obra de Herrería/Láser y máquina láser con costo de uso SIN mano de obra.
- Guarda piezas físicas, cantidad y medidas: metros desde centímetros; rendimiento por placa/cartón cuando corresponde; consumo directo para las demás. Sin merma añadida y sin volver a dividir por bulto. Tareas en segundos por unidad; para Láser transforma tiempo de 1/4 de placa y rendimiento a minutos por unidad, proporcional a las piezas, separando mano de obra y máquina. Rechaza tareas láser adicionales para revisar un posible doble cómputo.
- Utilidad sobre costo, IVA e IIBB de Resumen Producto, conservando cero explícito y utilidad ausente como pendiente con aviso. El costo de fabricación se recalcula con fuentes actuales sin IVA; IVA/IIBB se conservan en su configuración de producto para la etapa comercial, sin sumarlos nuevamente al despiece. Costos calculados PREPARATORIOS, sin activar precios ni publicaciones ni alterar la regla de neto mínimo.
- Vista previa: Crear / Conservar existente / Excluido / Revisar, costo neto y composición expandible. Avisos destacados antes de la tabla, tabla contenida con cabecera fija y progreso visible durante el análisis. Confirmación con el popup común, sin escribir acciones. Cancelar no guarda.
- Confirmación firmada durante 15 minutos y ligada a usuario/organización; revalida recursos, SKU y huella de costo. Una transacción para todo el lote, reversión total ante error. Cambios de precio o altas posteriores a la vista previa exigen analizar otra vez; repetir el lote conserva los existentes.
- Validación: 181 pruebas Python de maestro, datos generales, fabricación, despiece, consulta, duplicación, selectores e insumos/bultos aprobadas (21 específicas del nuevo importador). Incluyen SQL sin DML en vista previa, tenant/usuario/CSRF/firma/vencimiento, códigos de proveedor y ambigüedad, cancelación, rendimientos, impuestos/cero/ausentes, costos cambiados, concurrencia de SKU y rollback tras segunda ficha. DOM con HTML real: popup/cancelar sin envío/confirmar una vez/progreso/doble envío; sintaxis JS aprobada. QA visual real pendiente de staging.
- Ensayo aislado con PLANILLA GENERAL(3).xlsm y recursos/tarifas ficticios, sin base remota: 371 filas, 365 nuevas, PP6040H conservada y 5 llaveros excluidos; confirmación completa de las 365 aprobada. No representa los importes reales de staging ni afirma un UAT realizado allí.
- Avisos detectados: PC-FEN-001 no tiene utilidad en el origen (queda pendiente, sin inventar cero); ENCASTRE-A tiene dos piezas y requiere revisar el tiempo proporcional contra la fórmula histórica; BPPC01 no trae tareas y su confección tercerizada debe estar incluida en el insumo correspondiente. Revisarlos con las tarifas reales antes de confirmar.
- Siguiente UAT: deploy SOLO integración/staging, Ctrl+F5 → Base de Datos / Productos → Importar productos → Importar fabricación propia. Elegir Planilla General(3), unidad y recursos actuales; Analizar fabricación; verificar exclusiones, existentes, avisos y comparar PP6040H por el ojo. Si sólo PP6040H existe entre los SKU del archivo: 365 crear / 1 conservar / 5 excluir / 0 revisar. Si faltan recursos/costos se corrigen en los módulos existentes y se vuelve a analizar; no confirmar con importes supuestos. Confirmar una vez y revisar una ficha de Herrería y otra Láser por ojo/engranaje. Volver a analizar para comprobar que se conservan los ya importados.
- Sin Shell/migración nueva, despliegue automático ni conexiones externas nuevas. Producción/main, pedidos operativos, stock y scheduler fuera de alcance.

## 2026-10-20 — Orden visual de importación de fabricación
- Base oficial: `9f437c214d3ea9e87244786ff925ef57b76b8657`. Captura image(20261020-233850).png revisada: cinco controles en una misma fila, etiqueta larga de máquina desalineando campos y selector de archivo nativo poco cuidado.
- Se separan Archivo y unidad (dos columnas) y Tarifas de fabricación (tres columnas), con tarjetas suaves, numeración, alturas uniformes y ayudas bajo los selectores. Máquina láser conserva la advertencia de costo sin mano de obra en su ayuda. En pantallas estrechas cada grupo pasa a una columna; no se vuelven a juntar los cinco campos al cambiar zoom.
- Usos en opciones compactas con estados de selección y foco; selector de archivo con botón integrado; alcance resumido arriba y explicación técnica en detalle cerrado por defecto. Acción Analizar fabricación alineada a la derecha, ancho ajustado y progreso visible. CSS limitado a este importador y versión de recurso actualizada.
- Conserva nombres, valores, selección de archivo, tarifas, usos, rutas, validaciones, firma, cancelación y popup del importador existente. No modifica datos ni lógica de cálculo.
- Validación: 21 pruebas Python del importador aprobadas. DOM con HTML nuevo: revisión y detalles, popup, cancelar sin envío, confirmar una vez, progreso y prevención de doble envío aprobados. La comprobación visual en navegador real queda para staging.
- UAT: desplegar en integración/staging, Ctrl+F5 → Base de Datos / Productos → Importar productos → Importar fabricación propia. Revisar alineación, selector de archivo, tarjetas y ancho de pantalla; luego continuar con Analizar fabricación. No requiere Shell ni migración. Producción fuera de alcance.

## 2026-10-20 — Evitar agotamiento del proceso en fabricación masiva
- Base oficial: `7ca21847198434d8cc9c0f743b669ef475b2e4c7`. Incidente reportado: Gunicorn abortó el worker mientras consultaba exigir_uso_insumo; SystemExit y posterior SIGKILL. El texto “Perhaps out of memory?” es una sugerencia del servidor, no prueba de OOM. El fragmento no incluye la línea inicial del aborto.
- Medición reproducida con el archivo autorizado y base SQLite aislada, recursos/tarifas ficticios: análisis 7.401 operaciones SQL (3.393 SELECT y 4.008 PRAGMA); confirmación 33.301 operaciones (incluía consultas, inspecciones, escrituras y borrados innecesarios para altas nuevas). El ensayo anterior sin latencia no representaba la ida y vuelta a PostgreSQL de staging.
- Lectura de lote local a cada fase: recursos, unidad, disponibilidad de esquema y resultado de la misma validación de habilitaciones se reutilizan por identidad/unidad durante ese análisis. Sin caché global ni entre usuarios/peticiones. Rechaza sesión/organización distintas y escrituras ORM pendientes. Confirmar crea una lectura nueva y vuelve a validar precios y habilitaciones. El alta/edición manual conserva las consultas habituales por defecto; no se modifica producto_habilitaciones ni sus reglas.
- Persistencia agrupada exclusiva para ALTAS de fabricación ya normalizadas: inserciones por tabla y RETURNING con SKU/producto para recuperar identidades sin suponer el orden de respuesta SQL. Misma identidad Producto, ficha, datos generales, perfil, piezas/tareas, composición y snapshot de costo preparatorio. Conserva los SKU existentes y los cinco excluidos; no admite vínculos de insumo, combos, costo manual ni relaciones comerciales dentro de esta vía.
- Cálculos y permisos siguen usando los servicios existentes antes de escribir. Snapshot y despiece coinciden con la edición manual y su huella real, incluidos tiempos, orden y decimales. Una única transacción; cualquier fallo, incluso en los detalles finales, revierte todos los productos. La restricción única de SKU sigue cubriendo altas concurrentes. Comparación de SKU literal, sin tratar guiones bajos como comodines SQL.
- Resultado con el mismo lote: análisis 238 operaciones; confirmación 213 operaciones, de ellas 10 INSERT agrupados y sin UPDATE/DELETE. Se crearon 365 productos, conservó PP6040H y excluyó los cinco llaveros. Ensayo con demora artificial de 5 ms por operación: aproximadamente 1,4 s de análisis y 1,3 s de confirmación. Son mediciones locales, no promesa de latencia ni prueba de disponibilidad de Render.
- Se agregan logs de inicio/fin, cantidad y duración de análisis/confirmación, sin nombres, contenido del libro ni tokens. Permiten ubicar la fase si staging vuelve a interrumpir el proceso.
- Validación: 190 pruebas dirigidas aprobadas (27 de importación, incluida regresión de consultas acotadas para 100 altas, motor manual vs lote, permisos cambiados, costos cambiados, tenant, CSRF, firma, concurrencia y rollback final). Verificación de cancelación/popup previa se conserva; no cambia HTML/JS/CSS en este bloque. Prueba del archivo completo aislada y listado posterior HTTP 200; pendiente reintento real en PostgreSQL/Render.
- Ampliación a comprobaciones históricas fuera de estos cambios encontró tres fallos: test_modelos_y_panel_son_modulares lee app.py ausente del checkout parcial; test_listados_productivos_quedan_plegados_y_los_insumos_en_tabla exige una versión CSS antigua; test_listados_productivos_similares_usan_tablas_y_accion_gestionar exige un selector JS antiguo. Esos archivos no se modifican en este bloque y no se alteran tales pruebas para hacerlas pasar. La selección de 190 cubre los recorridos afectados y contratos de cálculo/exportación pertinentes.
- Siguiente UAT: desplegar este commit SOLO en integración/staging. Ctrl+F5 → Base de Datos / Productos → Importar productos → Importar fabricación propia. Volver a elegir archivo, unidad, tarifas válidas y máquina; Analizar fabricación; revisar totales/avisos; confirmar una vez cuando no haya errores. Comprobar una ficha de cada línea con el ojo y su edición. Si Render falla otra vez, revisar los logs de inicio/fin y el encabezado anterior al aborto. No requiere Shell, migración, aumento de timeout ni activación de conexiones; producción, scheduler y movimientos de stock fuera de alcance.

## 2026-10-20 — Exportar para editar y reimportar la misma planilla Fierro
- Base oficial: `bf96282e78a8025d3abf2041a427f613a82ce330`. Pedido: revisar el maestro completo en Excel, corregirlo manualmente y volver a importarlo con un contrato compatible. No se afirma que la confirmación del lote previo haya concluido: la última captura sólo validó el análisis (365 crear / 1 conservar / 5 excluir / 0 errores).
- Productos incorpora Exportar para editar y, dentro de Importar productos, Actualizar desde planilla Fierro. El XLSX se genera desde los datos actuales de la organización, no desde el Excel histórico ni los 100 resultados visibles. Hasta 500 productos por archivo; el límite se informa sin truncar la descarga.
- Contrato versionado FIERRO-PRODUCTOS-1 compartido por exportador e importador. Productos incluye identidad, nombre/descripción, tipo/unidad, estado, usos, No stockeable, stock negativo, logística, clasificación, marca, moneda/costo simple, IVA, IIBB y utilidad/base. Componentes y Tareas conservan las medidas y tiempos reales; Consumos/Operaciones representan fichas anteriores sin despiece; Maquinas e Indirectos preservan sus recursos, cantidades y observaciones. Perfiles distingue todas las unidades; Combos permite editar componentes/cantidades sin reutilizar el SKU del simple. Proveedores, Ubicaciones y Barras representan las relaciones existentes.
- Encabezados legibles, filtros, paneles inmovilizados, filas alternadas y celdas editables azules. Identidades y huella de versión ocultas/protegidas por validación; SKU/tipo/vínculo de insumo y pertenencia/modo/unidad de los perfiles se conservan en esta vía. Referencias ofrece identificadores y nombres de los recursos existentes. Costos de referencia muestra historial, moneda/unidad, estado/vigencia y costo sin IVA; Imágenes de consulta muestra archivos y acceso autenticado. Estas hojas son de consulta, sin modificar recursos, imágenes ni historial. La planilla no incorpora ni modifica existencias, movimientos ni precios publicados.
- Importación sólo de productos existentes: no crea ni duplica SKU, ni elimina productos por filas omitidas. Se conservan todas las hojas y encabezados; las filas relacionadas deben pertenecer a SKU incluidos. Borrar una fila de componente/tarea/relación permite corregir su lista, con los mismos límites y guardias del maestro; no se pueden agregar/eliminar perfiles. Para dejar de usar un producto se puede cambiar Activo. Los campos vacíos del formato completo son valores vacíos, no el mecanismo de conservar del importador básico; las imágenes siempre se conservan desde su identidad actual.
- Reimportar una exportación sin editar produce Sin cambios y cero INSERT/UPDATE/DELETE, incluso en productos sin datos generales anteriores. Distingue vacío, cero y falso; conserva barras y códigos de proveedor con ceros iniciales y cantidades de precisión alta como texto cuando Excel no podría representar todos sus dígitos. Importes y porcentajes editables se expresan sin IVA y en puntos porcentuales (21, 3.5, 90). Las fórmulas del usuario se rechazan; textos exportados se escriben como texto, sin fórmulas ejecutables.
- Vista previa con Actualizar / Sin cambios / Revisar, campos modificados, detalle antes/después y costo recalculado de recetas modificadas. Se usa el popup común, sin escribir frases; cancelar no guarda. Revisión firmada durante 15 minutos por usuario/organización; el archivo incorpora su organización y la huella de la ficha al exportar. Una descarga vieja no sobrescribe cambios posteriores; confirmación vuelve a validar todas las fichas, relaciones, permisos y costos antes de escribir. Una transacción, reversión total ante fallo final y sin activar costos/precios.
- Reutiliza normalizadores, guardias de ficha/stock, validación de datos generales, perfiles/composición de combos y motor de fabricación. Se extrae validar_datos_generales de la escritura manual para compartir su validación pura. Las correcciones escalares y las recetas se persisten agrupadas; se conservan identidades de líneas existentes, despiece y huella real, y sólo se agrega versión preparatoria de costo si cambia su snapshot. La lectura de despieces también se agrupa, con aislamiento por perfiles/org, evitando consultas por producto en exportación/listado. No se agrega otra base ni otro motor de costos.
- El importador básico detecta este formato y deriva al flujo correcto mediante mensaje, evitando aplicar sólo algunas columnas. La importación histórica de Planilla General se mantiene para altas y sigue conservando SKU existentes; no sirve para corregir productos ya cargados.
- Validación: 210 pruebas dirigidas aprobadas (20 de ida/vuelta XLSX), incluyendo no-op sin DML; atributos/IVA/utilidad; cambios agrupados; piezas/tiempos y costo; fichas anteriores; múltiples unidades; combo; moneda/costo simple; barras/proveedores/imágenes; revisión antigua; costo cambiado; tenant/usuario/firma/CSRF de rutas existentes; fórmulas; hojas faltantes; recurso ajeno; perfil eliminado; rollback tras inserciones finales; historial sin duplicación. DOM con HTML real: descarga, revisión, antes/después, popup, cancelar sin envío, confirmar una vez, progreso y doble envío; regresiones DOM de consulta/duplicación aprobadas. Sintaxis Python/JS aprobada. Verificación visual real de Excel y staging pendiente.
- Ensayo con los 366 SKU en base aislada y recursos ficticios: exportación, edición de utilidad de los 366 y confirmación 366 actualizar / 0 sin cambios, sin duplicar identidades. Con demora artificial de 5 ms por SQL: descarga ~5,4 s, revisión ~3,2 s, confirmación ~3,4 s. Mediciones locales SQLite, no promesa de tiempos PostgreSQL/Render. Las consultas posteriores por lote no reintroducen el recorrido de decenas de miles de operaciones del incidente anterior.
- UAT siguiente: deploy sólo integración/staging → Ctrl+F5 → Base de Datos / Productos → Exportar para editar. Primero guardar y subir el archivo SIN editar mediante Actualizar desde planilla Fierro: todos Sin cambios, sin necesidad de confirmar. Luego editar nombre/utilidad de un producto y una medida/cantidad de un componente; guardar XLSX, revisar antes/después/costo, probar Cancelar y volver a subir para confirmar. Consultar el producto con el ojo y exportar de nuevo para comparar. No modificar las columnas técnicas ni usar el importador histórico para esta corrección. No requiere Shell ni migraciones; producción/main, APIs externas, scheduler y movimientos de stock fuera de alcance.
