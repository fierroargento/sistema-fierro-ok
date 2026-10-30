# Dólar general y desgaste láser común

## Preparación en staging

Después del deploy manual, con laboratorio desconectado y rama de integración:

```bash
python -m scripts.preparar_cotizaciones --staging
```

Crea únicamente las tablas aditivas de cotización y configuración de desgaste. No carga un dólar predeterminado, máquinas, costos ni datos de producción. Es idempotente y no importa app.py ni inicia scheduler.

## Uso

1. Administración → Cotizaciones → Dólar general → Gestionar. Ingresar pesos por USD 1, fecha y referencia del dólar utilizado para costos. Confirmar con botones. La cotización es manual y común a las unidades de la misma empresa; otras organizaciones mantienen su propia cotización. No hay consulta externa ni cotización automática.
2. Con Fierro como unidad activa, abrir Gestionar en Desgaste láser común. Se proponen los datos de Planilla General(3): tubo USD 1.500, espejos USD 20 y lente USD 70; cada uno con vida útil de 8.000 horas. Revisar y confirmar. El dato 1.500 de este formulario es el precio USD del tubo, NO la cotización ARS/USD.
3. Se crea un único recurso de costo común `Corte láser — Mega Láser / Benelli`, propio de la unidad, que puede seleccionarse en las composiciones. No representa dos altas de máquinas físicas y no reemplaza ni reutiliza el registro sintético de UAT. La configuración tiene su propio historial y puede actualizarse desde el mismo emergente.
4. Los costos de fabricación que usan ese recurso calculan el desgaste con la cotización general vigente. La mano de obra se obtiene por separado desde Personal. Si no hay dólar cargado, el cálculo queda pendiente: no se toma 1.500 ni cero como respaldo.

Fórmula: suma de (USD de reposición de cada consumible / vida útil en horas / 60) × ARS por USD. El cálculo usa Decimal; el motor de costos conserva su precisión canónica de centavos por minuto. Los valores USD/vidas útiles se conservan para volver a calcular con otra cotización.

Con los datos de la planilla y un dólar de prueba de ARS 1.500, el valor exacto es ARS 4,96875/min y el motor utiliza ARS 4,97/min. Ese dólar sólo se usa en las pruebas: la aplicación no lo carga por defecto.

## Históricos y alcance

- Guardar un dólar nuevo conserva las versiones anteriores. Cambia la referencia que se usa al calcular nuevamente; no reescribe costos históricos, no activa versiones preparatorias y no publica precios de venta ni ejecuta movimientos de caja/stock.
- El detalle del costo calculado registra la versión y valor del dólar, fecha y versión de configuración usados. Una versión ya guardada conserva sus importes. Los controles existentes comparan de nuevo el cálculo al guardar una ficha.
- La cotización general se comparte a nivel de empresa por decisión del usuario; la configuración y el recurso láser se separan por unidad. El acceso actual es sólo administrador. El precio es una referencia manual de costos, no una integración con bancos/ARCA.
- Este desgaste cubre únicamente tubo, espejos y lente. Energía, mantenimiento y demás costos de máquina continúan pendientes, explícitos en la pantalla y en el detalle. No se incorpora otra vez la mano de obra de la planilla histórica.
- Las máquinas con tarifa convencional de adquisición/energía/mantenimiento siguen funcionando igual. El recurso láser dolarizado se gestiona desde Cotizaciones; se bloquea la carga paralela de una tarifa convencional sobre él.
- Cancelar, cerrar o consultar no guarda. Una edición abierta con dólar/configuración anteriores se rechaza para revisar. Fechas inválidas/futuras/anteriores a la vigente, importes no positivos/no finitos, vidas útiles inválidas e IDs ajenos se rechazan. No se permite un cambio de dólar que haga desbordar un cálculo de desgaste ya configurado.

## Traslado pendiente

El traslado UAT → Fierro NO se ejecuta al preparar este módulo o cargar el dólar. Después de configurar el recurso común, estará disponible como reemplazo real de la máquina sintética en la simulación del traslado. La mano de obra debe reasignarse a las áreas reales de Herrería/Láser. La separación de las bases de Render aún requiere comprobación antes de aplicar el traslado.
