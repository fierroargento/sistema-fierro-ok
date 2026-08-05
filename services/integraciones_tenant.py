"""
Resolucion tenant de cuentas de canales comerciales.

VinculoCanalComercial es la unica capa de pertenencia:
las credenciales originales permanecen globales y cada
cuenta externa puede estar vinculada a un solo tenant.
"""

from services.vinculos_canales import (
    CANAL_MERCADO_LIBRE,
    CANAL_TIENDA_NUBE,
    normalizar_canal,
)


ESTADO_ACTIVO = "activo"


def _organizacion_id(organizacion):
    valor = getattr(
        organizacion,
        "id",
        organizacion,
    )

    try:
        valor = int(valor)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "La organización no es válida."
        ) from error

    if valor <= 0:
        raise ValueError(
            "La organización no es válida."
        )

    return valor


def obtener_vinculos_canal_tenant(
    organizacion,
    *,
    VinculoCanalComercial,
    canal=None,
    solo_activos=False,
):
    organizacion_id = _organizacion_id(
        organizacion
    )

    consulta = (
        VinculoCanalComercial.query
        .filter_by(
            organizacion_id=organizacion_id
        )
    )

    if canal is not None:
        consulta = consulta.filter_by(
            canal=normalizar_canal(canal)
        )

    if solo_activos:
        consulta = consulta.filter_by(
            estado=ESTADO_ACTIVO
        )

    return list(
        consulta.all()
        or []
    )


def cuentas_mercado_libre_tenant(
    organizacion,
    *,
    VinculoCanalComercial,
    solo_activas=False,
):
    vinculos = obtener_vinculos_canal_tenant(
        organizacion,
        VinculoCanalComercial=(
            VinculoCanalComercial
        ),
        canal=CANAL_MERCADO_LIBRE,
        solo_activos=solo_activas,
    )

    return [
        vinculo.mercado_libre_cuenta
        for vinculo in vinculos
        if getattr(
            vinculo,
            "mercado_libre_cuenta",
            None,
        )
        is not None
    ]


def cuentas_tienda_nube_tenant(
    organizacion,
    *,
    VinculoCanalComercial,
    solo_activas=False,
):
    vinculos = obtener_vinculos_canal_tenant(
        organizacion,
        VinculoCanalComercial=(
            VinculoCanalComercial
        ),
        canal=CANAL_TIENDA_NUBE,
        solo_activos=solo_activas,
    )

    return [
        vinculo.tienda_nube_cuenta
        for vinculo in vinculos
        if getattr(
            vinculo,
            "tienda_nube_cuenta",
            None,
        )
        is not None
    ]


def exigir_vinculo_cuenta_tenant(
    organizacion,
    cuenta,
    *,
    canal,
    VinculoCanalComercial,
    solo_activo=False,
):
    if cuenta is None:
        raise ValueError(
            "No se recibió la cuenta del canal."
        )

    cuenta_id = getattr(
        cuenta,
        "id",
        None,
    )

    if cuenta_id is None:
        raise ValueError(
            "La cuenta del canal no es válida."
        )

    organizacion_id = _organizacion_id(
        organizacion
    )
    canal = normalizar_canal(canal)

    filtros = {
        "organizacion_id": organizacion_id,
        "canal": canal,
    }

    if canal == CANAL_MERCADO_LIBRE:
        filtros[
            "mercado_libre_cuenta_id"
        ] = cuenta_id
    else:
        filtros[
            "tienda_nube_cuenta_id"
        ] = cuenta_id

    if solo_activo:
        filtros["estado"] = ESTADO_ACTIVO

    vinculo = (
        VinculoCanalComercial.query
        .filter_by(**filtros)
        .first()
    )

    if vinculo is None:
        raise ValueError(
            "La cuenta no pertenece a la "
            "organización activa."
        )

    return vinculo


def asegurar_vinculo_ml_oauth(
    organizacion,
    unidad_negocio,
    cuenta,
    *,
    VinculoCanalComercial,
    db_session,
):
    """
    Crea el vinculo preparatorio de una cuenta ML.

    Un vinculo nuevo siempre nace desactivado.
    Un vinculo existente nunca se reasigna ni cambia
    de estado durante OAuth.
    """
    organizacion_id = _organizacion_id(
        organizacion
    )

    unidad_id = getattr(
        unidad_negocio,
        "id",
        None,
    )
    unidad_organizacion_id = getattr(
        unidad_negocio,
        "organizacion_id",
        None,
    )

    if (
        unidad_id is None
        or unidad_organizacion_id
        != organizacion_id
    ):
        raise ValueError(
            "La unidad de negocio no pertenece "
            "a la organizacion activa."
        )

    cuenta_id = getattr(
        cuenta,
        "id",
        None,
    )

    if cuenta_id is None:
        raise ValueError(
            "La cuenta de Mercado Libre todavia "
            "no tiene identificador."
        )

    vinculo = (
        VinculoCanalComercial.query
        .filter_by(
            mercado_libre_cuenta_id=cuenta_id
        )
        .first()
    )

    if vinculo is not None:
        if (
            getattr(
                vinculo,
                "canal",
                None,
            )
            != CANAL_MERCADO_LIBRE
            or getattr(
                vinculo,
                "organizacion_id",
                None,
            )
            != organizacion_id
            or getattr(
                vinculo,
                "unidad_negocio_id",
                None,
            )
            != unidad_id
        ):
            raise ValueError(
                "La cuenta de Mercado Libre ya "
                "pertenece a otro vinculo comercial."
            )

        return vinculo, False

    identificacion = str(
        getattr(
            cuenta,
            "nickname",
            None,
        )
        or getattr(
            cuenta,
            "user_id_ml",
            None,
        )
        or cuenta_id
    ).strip()

    nombre = (
        f"Mercado Libre - {identificacion}"
    )[:150]

    vinculo = VinculoCanalComercial(
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_id,
        canal=CANAL_MERCADO_LIBRE,
        mercado_libre_cuenta_id=cuenta_id,
        nombre=nombre,
        estado="desactivado",
        detalle=(
            "Vinculo preparatorio creado "
            "automaticamente desde OAuth."
        ),
    )

    db_session.add(vinculo)

    return vinculo, True
