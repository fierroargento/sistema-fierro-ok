# Remediación de reauditoría sobre 786dac0

Fecha: 2026-09-24

## Estado

Bloque preparado y validado localmente. No se desplegó, no se inició staging,
no se ejecutaron migraciones remotas y no se modificaron producción, su base ni
`origin/main`.

## Hallazgos corregidos

- N-01: la detección de secretos reconoce nombres segmentados y evita falsos
  positivos como `PASSENGER_APP_ENV`; también protege portadores sensibles como
  `CLOUDINARY_URL`, `TN_STORE_ID` y `WHATSAPP_PHONE_NUMBER_ID`.
- N-02: el parser monetario admite múltiples separadores de miles, por ejemplo
  `1.500.000`, y mantiene el rechazo de la forma ambigua `1.500`.
- N-03: las contraseñas rechazan espacios al comienzo o al final.
- N-04: una base sólo puede marcarse como vacía si no contiene tablas, vistas,
  vistas materializadas, secuencias ni rutinas de usuario.
- H-14: las sesiones tienen versión por usuario y antigüedad máxima de 12 horas;
  cerrar sesión o cambiar la contraseña invalida las copias anteriores.
- H-16: cerrar sesión e imprimir etiquetas son operaciones `POST` protegidas con
  CSRF; se eliminaron las mutaciones correspondientes por `GET`.
- H-18: los ítems de pedidos se construyen con nodos DOM y `textContent`, sin
  insertar SKU ni descripción mediante `innerHTML`.
- H-28: los archivos legacy se autorizan por nombre base exacto dentro de los
  pedidos visibles para el tenant y la unidad, sin búsquedas SQL por subcadena.

## Compatibilidad de esquema

Se agregó `usuarios_sistema.session_epoch` con valor inicial cero y la versión
de esquema `2026_09_24_seguridad_uat_bloque_3`. El readiness exige esta versión.
El bootstrap conserva separada la versión inicial para no repetir el backfill de
membresías durante una actualización.

## Validación local

- Suite completa: `2997 passed`.
- Compilación de módulos modificados: aprobada.
- `git diff --check`: aprobado.
- Remoto verificado antes del cierre: `origin/main` en `510ff063...` e
  `integracion-saas-2026-09` en `08ef406...`.

## Alcance

Este bloque mejora el aislamiento y la seguridad para la futura UAT. No declara
el CRM SaaS listo para producción. Los demás hallazgos de la auditoría siguen
abiertos y el arranque de staging requiere todavía la configuración y el control
previo definidos en `docs/STAGING_SEGURO_RUNBOOK.md`.
