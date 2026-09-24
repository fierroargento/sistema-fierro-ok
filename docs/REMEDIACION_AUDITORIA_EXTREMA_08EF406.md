# Remediación de auditoría extrema sobre 08ef406

Fecha: 2026-09-24

## Estado

Bloque preparado localmente. No se desplegó, no se ejecutó contra Render y no
se modificó `origin/main` ni la base productiva.

## Hallazgos bloqueantes corregidos

- B-01/H-01: una base con tablas ya existentes no puede marcarse como staging;
  la identidad canónica usa recurso Render, base y usuario, por lo que un alias
  interno/externo no cambia la identidad.
- B-02/H-02: Render o una base no local exigen un entorno declarado exactamente
  como `staging` o `produccion`.
- B-03/H-03: el bootstrap inicial sólo vincula usuarios sin ninguna membresía,
  no hereda el rol global y no repite el backfill después de registrar la versión.
- B-04/H-04: la edición completa de pedidos usa una lista blanca y no acepta
  ownership, unidad, cuentas, estados ni campos técnicos de canales.
- B-05/H-05: los errores se autoescapan; los scripts usan nonce CSP y
  `script-src` ya no admite scripts inline generales.
- B-06/H-06: las rutas de diagnóstico y asignación legacy global quedan
  desactivadas con 404 para cualquier tenant.
- B-07/H-07: staging rechaza variables con patrón de credencial salvo una lista
  blanca mínima; `/ready` rechaza cuentas ML que contengan tokens.
- H-08: `/ready` exige versión completa, marcador válido, commit exacto esperado,
  laboratorio desconectado, almacenamiento aislado y ausencia de tokens ML.

## Refuerzos previos a UAT incluidos

- H-11: autorización de edición usa el rol de la membresía activa.
- H-12: importes argentinos con miles y decimales se interpretan de manera
  uniforme; valores ambiguos como `1.500` se rechazan.
- H-13: altas web exigen contraseñas de 12 caracteres, letras y números, y
  rechazan contraseñas comunes.

## Configuración nueva requerida antes de cualquier arranque de staging

- `BASE_PRODUCTIVA_IDENTIDADES_SHA256`: identidad canónica de producción.
- `SISTEMA_FIERRO_COMMIT_ESPERADO`: hash completo del commit exacto desplegado.

La variable antigua `BASE_PRODUCTIVA_IDENTIDAD_SHA256` no habilita el arranque.
La ausencia de cualquiera de las nuevas condiciones produce rechazo seguro.

## Validación local

- Suite completa: `2994 passed`.
- Pruebas negativas nuevas: entorno fail-closed, base no vacía, membresías entre
  tenants, lista blanca de pedido, XSS/CSP, readiness, contraseñas y dinero.

## Pendientes no incluidos en este bloque

Los hallazgos H-09, H-10, H-14 a H-33 continúan abiertos salvo H-11, H-12 y H-13.
En particular, antes de un piloto real deben resolverse la propiedad de canales,
la selección ML por tenant, invalidación de sesiones, mutaciones por GET,
limitación detrás del proxy, archivos legacy y cifrado de tokens. Estos pendientes
no impiden revisar este bloque, pero sí impiden declarar el SaaS listo para operar.
