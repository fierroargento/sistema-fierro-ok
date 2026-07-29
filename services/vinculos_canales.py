"""
Validación y estados de vínculos con canales comerciales.
"""

from services.modulos_organizacion import (
    ESTADO_ACTIVO,
    ESTADO_DESACTIVADO,
    ESTADO_PRUEBA,
    normalizar_estado_modulo,
)


CANAL_MERCADO_LIBRE = "mercadolibre"
CANAL_TIENDA_NUBE = "tiendanube"

CANALES_COMERCIALES = frozenset(
    {
        CANAL_MERCADO_LIBRE,
        CANAL_TIENDA_NUBE,
    }
)


def normalizar_canal(canal):
    canal_normalizado = str(
        canal or ""
    ).strip().lower()

    if canal_normalizado not in CANALES_COMERCIALES:
        raise ValueError(
            "Canal comercial inválido."
        )

    return canal_normalizado


def validar_cuenta_exclusiva(
    canal,
    *,
    mercado_libre_cuenta=None,
    tienda_nube_cuenta=None,
):
    canal = normalizar_canal(canal)

    if canal == CANAL_MERCADO_LIBRE:
        if mercado_libre_cuenta is None:
            raise ValueError(
                "Seleccioná una cuenta de Mercado Libre."
            )
        if tienda_nube_cuenta is not None:
            raise ValueError(
                "Un vínculo ML no puede incluir "
                "una cuenta Tienda Nube."
            )

    if canal == CANAL_TIENDA_NUBE:
        if tienda_nube_cuenta is None:
            raise ValueError(
                "Seleccioná una cuenta Tienda Nube."
            )
        if mercado_libre_cuenta is not None:
            raise ValueError(
                "Un vínculo Tienda Nube no puede "
                "incluir una cuenta ML."
            )

    return True


def validar_pertenencia_organizacion(
    organizacion_id,
    *,
    unidad_negocio,
    catalogo=None,
    sucursal=None,
    entidad_fiscal=None,
):
    if unidad_negocio is None:
        raise ValueError(
            "Seleccioná una unidad de negocio."
        )

    registros = (
        ("unidad de negocio", unidad_negocio),
        ("catálogo", catalogo),
        ("sucursal", sucursal),
        ("entidad fiscal", entidad_fiscal),
    )

    for nombre, registro in registros:
        if registro is None:
            continue

        if (
            getattr(
                registro,
                "organizacion_id",
                None,
            )
            != organizacion_id
        ):
            raise ValueError(
                f"El registro de {nombre} no pertenece "
                "a la organización."
            )

    if (
        catalogo is not None
        and getattr(
            catalogo,
            "unidad_negocio_id",
            None,
        )
        not in (
            None,
            unidad_negocio.id,
        )
    ):
        raise ValueError(
            "El catálogo pertenece a otra "
            "unidad de negocio."
        )

    return True


def validar_dependencias_activas(
    vinculo,
):
    """
    Requisitos para marcar un vínculo como activo.

    Este control no conecta el vínculo con producción.
    """
    unidad = getattr(
        vinculo,
        "unidad_negocio",
        None,
    )
    catalogo = getattr(
        vinculo,
        "catalogo",
        None,
    )
    sucursal = getattr(
        vinculo,
        "sucursal_operativa",
        None,
    )
    entidad = getattr(
        vinculo,
        "entidad_fiscal",
        None,
    )

    if (
        unidad is None
        or not bool(
            getattr(unidad, "activa", False)
        )
    ):
        raise ValueError(
            "La unidad de negocio debe estar activa."
        )

    if (
        catalogo is not None
        and str(
            getattr(catalogo, "estado", "")
            or ""
        ).strip().lower()
        != ESTADO_ACTIVO
    ):
        raise ValueError(
            "El catálogo debe estar activo."
        )

    if (
        sucursal is not None
        and not bool(
            getattr(sucursal, "activa", False)
        )
    ):
        raise ValueError(
            "La sucursal debe estar activa."
        )

    if entidad is not None:
        if not bool(
            getattr(entidad, "activa", False)
        ):
            raise ValueError(
                "La entidad fiscal debe estar activa."
            )
        if not bool(
            getattr(
                entidad,
                "facturacion_habilitada",
                False,
            )
        ):
            raise ValueError(
                "La entidad fiscal debe tener "
                "facturación habilitada."
            )

    canal = normalizar_canal(
        getattr(vinculo, "canal", "")
    )

    if canal == CANAL_MERCADO_LIBRE:
        cuenta = getattr(
            vinculo,
            "mercado_libre_cuenta",
            None,
        )
    else:
        cuenta = getattr(
            vinculo,
            "tienda_nube_cuenta",
            None,
        )

    if cuenta is None:
        raise ValueError(
            "El vínculo no tiene una cuenta asociada."
        )

    estado_conexion = str(
        getattr(
            cuenta,
            "estado_conexion",
            "",
        )
        or ""
    ).strip().lower()

    if estado_conexion != "conectada":
        raise ValueError(
            "La cuenta del canal debe estar conectada."
        )

    return True


def cambiar_estado_vinculo(
    vinculo,
    nuevo_estado,
    *,
    db_session,
    detalle=None,
    commit=True,
):
    if vinculo is None:
        raise ValueError(
            "No se recibió el vínculo comercial."
        )

    estado = normalizar_estado_modulo(
        nuevo_estado
    )

    if estado == ESTADO_ACTIVO:
        validar_dependencias_activas(
            vinculo
        )

    vinculo.estado = estado

    if detalle is not None:
        vinculo.detalle = str(
            detalle
        ).strip()[:500]

    if commit:
        try:
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    return vinculo


def vinculo_habilita_produccion(vinculo):
    """
    Guardia futura: solamente activo puede habilitarse.

    Actualmente ningún flujo productivo invoca esta función.
    """
    if vinculo is None:
        return False

    return (
        str(
            getattr(vinculo, "estado", "")
            or ""
        ).strip().lower()
        == ESTADO_ACTIVO
    )
