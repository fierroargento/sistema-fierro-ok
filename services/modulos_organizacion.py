"""
Registro y activación segura de módulos opcionales.
"""


ESTADO_DESACTIVADO = "desactivado"
ESTADO_PRUEBA = "prueba"
ESTADO_ACTIVO = "activo"

ESTADOS_MODULO = frozenset(
    {
        ESTADO_DESACTIVADO,
        ESTADO_PRUEBA,
        ESTADO_ACTIVO,
    }
)

MODULOS_INICIALES = (
    (
        "catalogos",
        "Catálogos comerciales",
    ),
    (
        "sucursales",
        "Sucursales operativas",
    ),
    (
        "facturacion-multicuit",
        "Facturación multi-CUIT",
    ),
    (
        "tiendanube-multicuenta",
        "Tienda Nube multicuenta",
    ),
    (
        "crm",
        "CRM comercial",
    ),
)


def normalizar_estado_modulo(estado):
    estado_normalizado = str(
        estado or ""
    ).strip().lower()

    if estado_normalizado not in ESTADOS_MODULO:
        raise ValueError(
            "Estado de módulo inválido: "
            f"{estado_normalizado or '(vacío)'}."
        )

    return estado_normalizado


def modulo_esta_activo(modulo):
    """
    Solo el estado activo habilita producción.

    El estado prueba queda disponible para futuras rutas
    controladas, pero no habilita operación productiva.
    """
    if modulo is None:
        return False

    return (
        str(
            getattr(modulo, "estado", "")
            or ""
        ).strip().lower()
        == ESTADO_ACTIVO
    )


def modulo_esta_en_prueba(modulo):
    if modulo is None:
        return False

    return (
        str(
            getattr(modulo, "estado", "")
            or ""
        ).strip().lower()
        == ESTADO_PRUEBA
    )


def cambiar_estado_modulo(
    modulo,
    nuevo_estado,
    *,
    db_session,
    detalle=None,
    commit=True,
):
    if modulo is None:
        raise ValueError(
            "No se recibió el módulo a modificar."
        )

    estado = normalizar_estado_modulo(
        nuevo_estado
    )

    modulo.estado = estado

    if detalle is not None:
        modulo.detalle = str(detalle).strip()[:500]

    if commit:
        try:
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    return modulo


def obtener_modulo_organizacion(
    ModuloOrganizacion,
    *,
    organizacion_id,
    codigo,
):
    codigo = str(codigo or "").strip().lower()

    if not codigo:
        return None

    return (
        ModuloOrganizacion.query
        .filter_by(
            organizacion_id=organizacion_id,
            codigo=codigo,
        )
        .first()
    )


def asegurar_modulos_iniciales(
    *,
    ModuloOrganizacion,
    organizacion_id,
    db_session,
    logger_fn=print,
):
    """
    Crea el registro de módulos sin habilitar ninguno.

    Es idempotente y no modifica estados ya configurados.
    """
    cambios = False
    modulos = {}

    for codigo, nombre in MODULOS_INICIALES:
        modulo = obtener_modulo_organizacion(
            ModuloOrganizacion,
            organizacion_id=organizacion_id,
            codigo=codigo,
        )

        if modulo is None:
            modulo = ModuloOrganizacion(
                organizacion_id=organizacion_id,
                codigo=codigo,
                nombre=nombre,
                estado=ESTADO_DESACTIVADO,
            )
            db_session.add(modulo)
            cambios = True

        modulos[codigo] = modulo

    if cambios:
        try:
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

        if logger_fn is not None:
            logger_fn(
                "[MÓDULOS] Registros iniciales "
                "creados en estado desactivado."
            )

    return {
        "modulos": modulos,
        "cambios": cambios,
    }
