"""
Inicialización idempotente de la estructura empresarial.
"""


ORGANIZACION_SLUG_GRUPO_FIERRO = "fierro-100-argento"

ORGANIZACIONES_INICIALES = (
    (
        "fierro-100-argento",
        "Fierro 100% Argento",
        "fierro-100-argento",
        "Fierro 100% Argento",
    ),
    (
        "nautica-del-plata",
        "Náutica del Plata",
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

    organizaciones = {}
    unidades = {}

    for slug, nombre_organizacion, codigo, nombre_unidad in ORGANIZACIONES_INICIALES:
        organizacion = Organizacion.query.filter_by(slug=slug).first()
        if organizacion is None:
            organizacion = Organizacion(
                nombre=nombre_organizacion,
                slug=slug,
                activa=True,
            )
            db_session.add(organizacion)
            db_session.flush()
            cambios = True
        organizaciones[slug] = organizacion
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
                nombre=nombre_unidad,
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
                "Organizaciones Fierro y Náutica aisladas con sus unidades."
            )

    return {
        "organizacion": organizaciones[ORGANIZACION_SLUG_GRUPO_FIERRO],
        "organizaciones": organizaciones,
        "unidades": unidades,
        "cambios": cambios,
    }
