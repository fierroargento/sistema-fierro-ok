# AGENTS.md — Sistema Fierro APB (VERSIÓN FINAL PARA REEMPLAZO)

**Proyecto**: Sistema de gestión de pedidos omnicanal (Flask + PostgreSQL)
**Enfoque**: A Prueba de Boludos (APB)
**Fuente de verdad**: app.py + domain/estados.py
**Estado**: VERSION SINCRONIZADA PARA PRODUCCIÓN
**Fecha**: 2026-05-21

---

# 🎯 OBJETIVO DEL SISTEMA

El sistema gestiona pedidos desde:

* Mercado Libre
* Tienda Nube
* WhatsApp (bot + operador)

Y coordina logística con:

* Andreani
* Correo Argentino
* Vía Cargo

El sistema NO es lineal: es un flujo híbrido operativo + logístico + comercial.

---

# ⚠️ REGLA FUNDAMENTAL APB

El estado real del pedido SIEMPRE es el definido en `domain.estados.Estado` y ejecutado en `app.py`.

❌ Este archivo no redefine lógica.
✔ Solo documenta el sistema real.

---

# 🧠 FLUJO REAL DE ESTADOS

## 🔵 CARGA

* Cargando Pedido

## 🟡 PREPARACIÓN

* Etiqueta Lista
* Etiqueta Impresa
* Embalado

## 🟠 DESPACHO

* Despachado
* Verificar llegada a destino

## 🔴 INCIDENTES

* Con demora de entrega
* Con reclamo en transporte

## ⚪ ENTREGA FINAL

* Listo para retirar
* Entregado

## ⚫ CASOS ESPECIALES

* No entregado
* Reclamar a Mercado Libre

---

# 🚨 REGLAS CRÍTICAS

## Mercado Libre

* “Entregado” en ML NO modifica automáticamente estado interno
* Solo webhook + validación del sistema actualiza estados

## Verificar llegada a destino

* Estado activo del flujo logístico
* No es decorativo

## Listo para retirar

* Estado operativo formal
* Tiene control por rol (carga/admin)

## Reclamos

* Con demora de entrega
* Con reclamo en transporte

Son estados distintos y no se fusionan.

---

# 🔁 LOGÍSTICA

Tracking externo:

* Andreani
* Correo Argentino
* Vía Cargo

Estados como "Verificar llegada" dependen de tracking real.

---

# 🤖 CANALES

Orden de control:

1. WhatsApp
2. Mercado Libre
3. Tienda Nube

Campos críticos:

* wa_estado
* ml_*
* tn_*

No deben modificarse sin migración completa.

---

# ⚙️ SCHEDULER

* sincronización ML
* recordatorios 24/48/72h
* timers WhatsApp

Reglas:

* UTC obligatorio
* errores aislados

---

# 🧪 DESARROLLO APB

Antes de cambios:

* revisar impacto en estados
* revisar tests
* validar scheduler

Tests críticos:

* motor_bloqueo
* ownership_canales
* despacho_mobile
* estado_service

---

# 🚨 ANTI-PATRONES

❌ Simplificar estados reales
❌ Cambiar estados sin actualizar domain.estados
❌ Romper scheduler
❌ Mezclar ML con estado interno
❌ Ignorar estados intermedios

---

# 📊 ARQUITECTURA

Sistema basado en grafo de estados:

* bifurcaciones logísticas
* control por canal
* intervención humana
* automatización parcial

---

# 🔐 FUENTE DE VERDAD

* domain/estados.py
* app.py
* services/pedidos_estado.py

---

# ⚠️ REGLA FINAL

Si hay conflicto:

👉 gana app.py siempre
