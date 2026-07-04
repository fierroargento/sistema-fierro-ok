# Plan de centralizacion Sistema Fierro

## Objetivo

Ordenar la logica operativa del sistema para evolucionar a SaaS/CRM/multicuenta sin romper produccion.

## Regla principal

No hacer big-bang refactor. Cada cambio debe ser chico, testeable y reversible.

## Orden final

1. Golden master de comportamiento actual.
2. Acciones UI/permisos.
3. Documento de decision sobre sucursales.
4. Motor de estado/bloqueos.
5. Decision centralizada de sucursal.
6. Transicion ML a WhatsApp.
7. Cross-sell / Canal Manager.

## Reglas de seguridad

- No borrar la funcion vieja en el mismo commit que crea la nueva.
- app.py debe delegar cada vez mas, no decidir.
- Los cambios operativos no deben depender de que se pueda enviar un mensaje.
- Canal Manager puede bloquear mensajes, no guardar datos.
- Cross-sell debe tener una politica unica de bloqueo/desbloqueo.
- No tocar webhooks grandes al inicio.
- No tocar modelos ni migraciones al inicio.
- No tocar deploy config al inicio.
- Cada extraccion debe tener tests antes de conectarse a produccion.

## Bloque 1 - UI / permisos

Centralizar:

- accion_sugerida_pedido
- accion_principal_pedido
- texto_boton_estado
- primer_paso_pendiente_carga
- puede_imprimir_pedido
- puede_editar_pedido
- puede_avanzar_segun_rol

Destino:

- services/pedidos_ui_actions.py
- services/pedidos_permisos.py

## Bloque 2 - Estado / bloqueos

Centralizar:

- puede_avanzar_pedido
- actualizar_estado_automatico
- despacho_completo
- puede_imprimir_acordas_entrega
- puede_imprimir_etiqueta_directamente
- motor_bloqueo
- siguiente_estado
- aplicar_estado_y_fechas

Destino:

- services/workflow/estado_pedido.py
- services/workflow/bloqueos_pedido.py

## Bloque 3 - Logistica conversacional

Centralizar:

- cliente eligio sucursal
- cliente consulto horarios
- cliente dio domicilio
- cliente corrigio CP
- sucursal confirmada
- transicion ML a WhatsApp

Destino:

- services/workflow/sucursal_decision.py
- services/workflow/transicion_ml_wa.py

## Bloque 4 - Cross-sell / Canal Manager

Centralizar:

- ofrecimiento cross-sell
- bloqueo de etiqueta lista
- excepcion trazable
- mensaje repetido
- politica de canal

Destino:

- services/workflow/cross_sell_orquestador.py
- services/policies/canal_manager_policy.py
