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
