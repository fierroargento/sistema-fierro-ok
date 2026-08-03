"""
Inicialización idempotente de la estructura empresarial.
"""


ORGANIZACION_SLUG_GRUPO_FIERRO = "grupo-fierro"

UNIDADES_INICIALES = (
    (
        "fierro-100-argento",
        "Fierro 100% Argento",
    ),
    (
        "nautica-del-plata",
        "Náutica del Plata",
    ),
)


def asegurar_estructura_empresarial_inicial(
    *,
    Organizacion,
    UnidadNegocio,
    db_session,
    logger_fn=print,
):
    """
    Garantiza la organización y sus unidades iniciales.

    No conecta integraciones, no asigna pedidos y no cambia
    el comportamiento operativo existente.
    """
    cambios = False

    organizacion = (
        Organizacion.query
        .filter_by(
            slug=ORGANIZACION_SLUG_GRUPO_FIERRO
        )
        .first()
    )

    if organizacion is None:
        organizacion = Organizacion(
            nombre="Grupo Fierro",
            slug=ORGANIZACION_SLUG_GRUPO_FIERRO,
            activa=True,
        )
        db_session.add(organizacion)
        db_session.flush()
        cambios = True

    unidades = {}

    for codigo, nombre in UNIDADES_INICIALES:
        unidad = (
            UnidadNegocio.query
            .filter_by(
                organizacion_id=organizacion.id,
                codigo=codigo,
            )
            .first()
        )

        if unidad is None:
            unidad = UnidadNegocio(
                organizacion_id=organizacion.id,
                nombre=nombre,
                codigo=codigo,
                activa=True,
            )
            db_session.add(unidad)
            cambios = True

        unidades[codigo] = unidad

    if cambios:
        db_session.commit()

        if logger_fn is not None:
            logger_fn(
                "[ESTRUCTURA EMPRESARIAL] "
                "Organización y unidades iniciales aseguradas."
            )

    return {
        "organizacion": organizacion,
        "unidades": unidades,
        "cambios": cambios,
    }
