# Decision de arquitectura - Sucursales

## Contexto

Durante la auditoria de centralizacion se detecto que la logica de sucursales esta repartida entre app.py, services y modules.

Hay dos familias de responsabilidades mezcladas:

1. Detectar que sucursal eligio el cliente.
2. Sugerir sucursales disponibles al cliente.

Ademas, esta logica se cruza con:
- Mercado Libre
- WhatsApp
- Via Cargo
- Correo Argentino
- cross-sell
- flags de IA
- avance de estado

El caso real que motivo esta decision fue un pedido ML Acordas + Via Cargo donde el cliente respondio "Sucursal Nro 2". El sistema primero no resolvio bien la opcion, luego guardo sucursal, pero la transicion ML a WhatsApp y cross-sell quedaron en caminos separados.

## Problema

Hoy existen funciones con responsabilidades parecidas:

### Deteccion de sucursal

- app.py / detectar_sucursal
- services/correo_sucursales_eleccion.py / detectar_sucursal_correo_ofrecida
- helpers relacionados en services/mensajes_sucursales.py

### Sugerencia de sucursales

- app.py / sugerir_sucursales
- modules/transportes/selector.py / sugerir_sucursales_correo_pedido
- servicios de Via Cargo / Correo

Esto genera riesgo de:
- reglas duplicadas,
- diferencias entre Correo y Via Cargo,
- deteccion distinta segun el canal,
- guardar datos operativos dependiendo de si se pudo mandar mensaje,
- bugs dificiles de rastrear.

## Decision

La logica futura se separa en tres niveles.

### 1. Decision pura de sucursal

Nuevo destino futuro:

services/workflow/sucursal_decision.py

Debe responder preguntas puras:

- el texto del cliente elige una sucursal?
- que opcion eligio?
- corresponde a una lista ofrecida?
- es una consulta y no una eleccion?
- hay sucursal unica?
- hay mensaje mixto: eleccion + consulta de horarios?
- que sucursal queda seleccionada?

No debe:
- mandar mensajes,
- hacer db.session.commit(),
- cambiar estado del pedido,
- iniciar WhatsApp,
- disparar cross-sell.

### 2. Aplicacion operativa al pedido

Nuevo destino futuro:

services/workflow/logistica_pedido.py

Debe aplicar al pedido el resultado de la decision:

- setear sucursal_nombre,
- setear direccion,
- setear localidad,
- setear provincia,
- limpiar faltantes,
- limpiar flags de sucursales ofrecidas,
- marcar datos completos si corresponde.

No debe:
- mandar mensajes externos,
- decidir canal,
- disparar cross-sell.

### 3. Orquestacion conversacional

Nuevo destino futuro:

services/workflow/transicion_ml_wa.py

Debe decidir:

- si se responde por Mercado Libre,
- si se inicia WhatsApp,
- si se dispara cross-sell,
- si se escala operador,
- si Canal Manager bloquea solo mensaje y no operacion.

## Regla clave

Guardar datos logisticos no debe depender de que se pueda enviar un mensaje automatico.

Canal Manager puede bloquear mensajes.
No puede bloquear guardar sucursal, limpiar faltantes o completar datos logisticos.

## Funcion ganadora para deteccion por opcion

Para seleccion por numero/opcion, la base ganadora sera:

services/mensajes_sucursales.py

Especialmente:
- normalizar_numero_opcion_sucursal
- extraer_opcion_sucursal_explicita
- seleccionar_sucursal_ofrecida_por_opcion

Motivo:
- ya soporta textos como "Sucursal Nro 2",
- puede trabajar sobre ids ofrecidas,
- sirve para Via Cargo y puede extenderse a Correo,
- es una funcion mas pura y testeable que hacerlo dentro de app.py.

## Funcion ganadora para Correo

Para Correo, la logica especifica de sucursales ofrecidas debe seguir saliendo de:

services/correo_sucursales_eleccion.py

Pero en el futuro debe ser llamada desde sucursal_decision.py como adaptador especifico de Correo, no directamente desde app.py.

## Funcion ganadora para Via Cargo

Para Via Cargo, la seleccion debe ir por:

services/mensajes_sucursales.py

y el catalogo/lista ofrecida debe resolverse desde sucursal_decision.py, no desde app.py.

## Politica para funciones viejas

No borrar funciones viejas en el mismo commit en que se crea la nueva.

Las funciones viejas deben quedar como fallback hasta que:
- existan tests de caracterizacion,
- el nuevo servicio pase los mismos casos,
- app.py delegue al nuevo servicio,
- se haya probado en produccion.

## Tests obligatorios antes de conectar a produccion

Casos minimos:

1. "Sucursal Nro 2"
2. "opcion 2"
3. "la 2"
4. "quiero la sucursal 2"
5. sucursal unica ofrecida
6. mensaje mixto: sucursal + consulta de horarios
7. mensaje que consulta horarios pero no elige sucursal
8. Correo con sucursal ofrecida
9. Via Cargo con sucursal ofrecida
10. opcion fuera de rango
11. texto ambiguo que debe pedir operador
12. reintento/idempotencia: misma eleccion recibida dos veces

## Criterio de rollback

Mientras app.py siga conservando las funciones viejas, el rollback debe ser simple:

- dejar de llamar al servicio nuevo,
- volver a detectar con la logica vieja,
- no borrar datos ya guardados.

## Decision final

La centralizacion de sucursales se hara con esta secuencia:

1. Documentar esta decision.
2. Crear service nuevo sin conectarlo.
3. Agregar tests de sucursal.
4. Conectar solo una ruta/camino controlado.
5. Mantener fallback viejo.
6. Recién despues evaluar limpieza de funciones viejas.
