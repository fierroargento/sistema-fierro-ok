# Preparación de staging desconectado

Este documento prepara un servicio de ensayo separado. No debe editarse el
servicio productivo ni reutilizarse su base PostgreSQL.

## Recursos que se crearán sólo con autorización posterior

1. Web Service nuevo, apuntado a `integracion-saas-2026-09`.
2. PostgreSQL nuevo y vacío, exclusivo del ensayo.
3. Variables basadas en `config/staging_desconectado.env.example`.

El comando de arranque será el mismo de la aplicación actual:
`gunicorn app:app`. La versión declarada del proyecto es Python 3.12.8.

## Preparación de la huella productiva

La persona administradora calcula localmente SHA-256 sobre la URL productiva y
carga sólo el resultado en `BASE_PRODUCTIVA_HUELLA_SHA256`. La URL no se copia
al servicio de ensayo. El certificador calcula la huella de `DATABASE_URL` del
staging y bloquea la aprobación si ambas coinciden.

## Preflight antes de cualquier prueba

Con las variables ya cargadas en el servicio de ensayo ejecutar:

`python scripts/certificar_staging_desconectado.py`

Debe terminar con código 0 y `aprobado: true`. El resultado no contiene URLs,
contraseñas ni `SECRET_KEY`. Esta certificación no abre la base, no hace
peticiones de red y no crea tablas.

## Condiciones obligatorias

- Nunca configurar auto-deploy desde `main` en el staging.
- Nunca compartir `DATABASE_URL` ni `SECRET_KEY` con producción.
- Mantener `MODO_LABORATORIO_DESCONECTADO=true` durante toda la UAT.
- Mantener en false conexiones, efectos, webhooks, scheduler y bootstrap.
- No cargar tokens productivos de ML, Tienda Nube, WhatsApp o transportes.
- El alta efectiva de recursos requiere aprobación expresa y verificación
  visual de nombre, rama, plan y base antes de confirmar.
