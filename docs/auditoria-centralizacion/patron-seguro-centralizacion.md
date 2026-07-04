# Patron seguro de centralizacion

Este proyecto tiene mucha logica historica concentrada en app.py. Para reducir riesgo, la centralizacion debe hacerse en pasos chicos y reversibles.

## Regla base

No mover una regla directamente desde app.py a un flujo nuevo sin antes crear un service puro y testeado.

Orden obligatorio:

1. Crear service puro.
2. Probar el service sin Flask, sin DB real y sin mensajes externos.
3. Conectar app.py con fallback al comportamiento anterior.
4. Agregar test estatico del punto conectado.
5. Validar py_compile de app.py antes de commit y antes de push.
6. Pushear recien cuando los tests minimos pasan.

## Services puros

Un service puro no debe:

- hacer db.session.commit
- enviar mensajes ML
- enviar mensajes WhatsApp
- registrar envios automaticos
- renderizar templates
- depender de request/session/current_user
- decidir permisos de UI

## app.py

Cuando se toque app.py:

- el diff debe ser chico
- debe mantenerse fallback cuando se reemplaza una regla operativa
- debe correr tests/test_app_py_compile_static.py
- debe revisarse git diff antes del commit

## Patron usado en sucursal Via Cargo

Primero se creo:

- services/workflow_sucursal_decision.py
- services/workflow_logistica_sucursal.py

Despues se conecto app.py en pasos separados:

1. aplicar sucursal elegida al pedido
2. centralizar resumen IA
3. usar decision central con fallback viejo

Este patron debe repetirse para Correo, ML/WA, cross-sell, estados y permisos.
