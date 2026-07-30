"""
Resolucion del tenant actual sin depender de Flask.

La sesion web solamente aporta un organizacion_id opcional.
La autorizacion real surge de UsuarioOrganizacion.
"""


class TenantError(RuntimeError):
    """Error base del contexto tenant."""


class TenantNoDisponible(TenantError):
    """El usuario no posee organizaciones activas."""


class TenantNoAutorizado(TenantError):
    """El usuario intento acceder a otro tenant."""


class TenantAmbiguo(TenantError):
    """Hay varias organizaciones y ninguna seleccion segura."""


def _id_positivo(valor):
    if valor in (None, ""):
        return None

    try:
        resultado = int(valor)
    except (TypeError, ValueError) as error:
        raise TenantNoAutorizado(
            "La organizacion solicitada no es valida."
        ) from error

    if resultado <= 0:
        raise TenantNoAutorizado(
            "La organizacion solicitada no es valida."
        )

    return resultado


def _membresia_operativa(membresia):
    if not bool(
        getattr(membresia, "activa", False)
    ):
        return False

    organizacion = getattr(
        membresia,
        "organizacion",
        None,
    )

    if organizacion is None:
        return True

    return bool(
        getattr(organizacion, "activa", False)
    )


def seleccionar_membresia_tenant(
    membresias,
    organizacion_id=None,
):
    """
    Selecciona una membresia autorizada.

    Con una sola membresia activa mantiene compatibilidad con
    la instalacion actual. Con varias exige una seleccion explicita
    o una unica membresia predeterminada.
    """
    activas = [
        membresia
        for membresia in list(membresias or [])
        if _membresia_operativa(membresia)
    ]

    if not activas:
        raise TenantNoDisponible(
            "El usuario no tiene organizaciones activas."
        )

    solicitada = _id_positivo(organizacion_id)

    if solicitada is not None:
        for membresia in activas:
            if (
                int(membresia.organizacion_id)
                == solicitada
            ):
                return membresia

        raise TenantNoAutorizado(
            "El usuario no pertenece a la organizacion."
        )

    if len(activas) == 1:
        return activas[0]

    predeterminadas = [
        membresia
        for membresia in activas
        if bool(
            getattr(
                membresia,
                "predeterminada",
                False,
            )
        )
    ]

    if len(predeterminadas) == 1:
        return predeterminadas[0]

    raise TenantAmbiguo(
        "Debe seleccionarse una organizacion."
    )


def resolver_tenant_usuario(
    usuario,
    *,
    UsuarioOrganizacion,
    organizacion_id=None,
):
    if usuario is None:
        raise TenantNoDisponible(
            "No hay un usuario autenticado."
        )

    membresias = (
        UsuarioOrganizacion.query
        .filter_by(
            usuario_id=usuario.id,
            activa=True,
        )
        .all()
    )

    return seleccionar_membresia_tenant(
        membresias,
        organizacion_id=organizacion_id,
    )


def asegurar_membresias_organizacion_inicial(
    *,
    UsuarioSistema,
    UsuarioOrganizacion,
    organizacion_id,
    db_session,
    usuarios=None,
    buscar_membresia_fn=None,
    logger_fn=print,
):
    """
    Vincula usuarios historicos con la organizacion inicial.

    Solo crea membresias. No activa modulos, integraciones,
    facturacion ni automatizaciones.
    """
    organizacion_id = _id_positivo(
        organizacion_id
    )

    if usuarios is None:
        usuarios = UsuarioSistema.query.all()

    if buscar_membresia_fn is None:
        def buscar_membresia_fn(
            usuario_id,
            organizacion_id_actual,
        ):
            return (
                UsuarioOrganizacion.query
                .filter_by(
                    usuario_id=usuario_id,
                    organizacion_id=(
                        organizacion_id_actual
                    ),
                )
                .first()
            )

    creadas = 0

    for usuario in list(usuarios or []):
        existente = buscar_membresia_fn(
            usuario.id,
            organizacion_id,
        )

        if existente is not None:
            continue

        membresia = UsuarioOrganizacion(
            usuario_id=usuario.id,
            organizacion_id=organizacion_id,
            rol=(
                getattr(usuario, "rol", None)
                or "carga"
            ),
            activa=bool(
                getattr(usuario, "activo", True)
            ),
            predeterminada=True,
        )
        db_session.add(membresia)
        creadas += 1

    if creadas:
        db_session.commit()

        if logger_fn is not None:
            logger_fn(
                "[TENANT] "
                f"Membresias iniciales creadas: {creadas}"
            )

    return creadas
