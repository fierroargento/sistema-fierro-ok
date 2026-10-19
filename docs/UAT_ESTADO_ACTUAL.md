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
