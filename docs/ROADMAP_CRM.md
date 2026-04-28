# CRM Fierro - Ancla y refactor liviano

## Objetivo
Convertir Sistema Fierro en CRM integral propio sin romper la operación actual.

## Regla de oro
Primero estabilidad operativa. Después arquitectura. Después CRM.

## Etapa actual: refactor liviano 1
- Se conserva `app.py` funcional.
- Se agregan carpetas objetivo: `services/`, `models/`, `routes/`.
- Se preparan helpers puros de Tienda Nube.
- No se cambian URLs ni flujo operativo.

## Próxima etapa
Extraer de a bloques:
1. Helpers puros TN.
2. Helpers puros ML.
3. Rutas admin/auth.
4. Servicios con dependencia a DB.

## No hacer todavía
- No mover modelos hasta tener migraciones controladas.
- No cambiar rutas públicas.
- No introducir API REST antes de entidad Cliente.
