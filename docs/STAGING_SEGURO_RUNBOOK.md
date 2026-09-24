# Staging seguro — procedimiento operativo

Este procedimiento **no debe ejecutarse sobre producción**. La rama de
remediación se prepara y prueba localmente; la publicación y el despliegue
requieren una autorización posterior y explícita.

## Barreras obligatorias

- `SISTEMA_FIERRO_ENTORNO=staging`.
- `MODO_LABORATORIO_DESCONECTADO=true`.
- Todas las llaves maestras de conexiones, efectos, webhooks, scheduler y
  bootstrap permanecen en `false` durante la ejecución normal.
- `OPERACIONES_MASIVAS_HABILITADAS=false`; sólo se abre temporalmente para una
  limpieza deliberada de datos de ensayo y vuelve a cerrarse inmediatamente.
- La URL, la identidad estable y el marcador interno de la base deben ser
  distintos de producción.
- Staging no recibe tokens de Mercado Libre, Tienda Nube, WhatsApp, OpenAI,
  Cloudinary ni Sentry.
- Las imágenes se guardan en un disco exclusivo mediante
  `ALMACENAMIENTO_ARCHIVOS=local_aislado`.

## Preparación futura de una base nueva

1. Crear una base PostgreSQL exclusiva y un disco persistente exclusivo.
2. Completar las variables documentadas en
   `config/staging_desconectado.env.example`.
3. Ejecutar el preflight sin red:

   `python scripts/certificar_staging_desconectado.py`

4. Sólo si el resultado es aprobado, marcar la base vacía:

   `python scripts/marcar_base_staging.py --confirmar "MARCAR BASE STAGING AISLADA"`

5. Inicializar el esquema mediante un proceso puntual, nunca en el arranque
   normal del servidor:

   `flask --app app inicializar-base-staging --confirmar "INICIALIZAR BASE STAGING AISLADA"`

6. Crear el primer administrador sin contraseña predeterminada:

   `flask --app app crear-admin-inicial`

7. Reiniciar con `BOOTSTRAP_BASE_DATOS_HABILITADO=false` y comprobar `/ready`.

## Paquete sintético para la futura UAT

El repositorio puede generar un ZIP reproducible sin abrir la base ni utilizar
la red:

`python scripts/generar_paquete_datos_uat.py --salida paquete_uat.zip`

El ZIP contiene inclusiones/producto, clasificación, insumos, empleados,
máquinas, costos fijos, ficha técnica, proveedores y una imagen artificial.
Incluye `LEEME_PRIMERO.txt` con el orden de carga y un manifiesto SHA-256.
La generación del archivo no autoriza su carga: sólo debe utilizarse después
de aprobar el preflight y sobre la organización/unidad exclusiva de ensayo.

## Resultado esperado

El servidor sólo queda listo si puede consultar la base marcada, mantiene el
laboratorio desconectado y utiliza almacenamiento local aislado. Cualquier
inconsistencia devuelve estado `not_ready` o impide el arranque.
