"""
Migraciones aditivas para la transicion SaaS.

No elimina columnas ni modifica flujos operativos.
"""


def organizacion_evento_legacy(
    evento,
    organizacion_id_predeterminada,
):
    borrador = getattr(
        evento,
        "borrador",
        None,
    )
    configuracion = getattr(
        evento,
        "configuracion",
        None,
    )

    if borrador is not None:
        organizacion_id = getattr(
            borrador,
            "organizacion_id",
            None,
        )
        if organizacion_id:
            return int(organizacion_id)

    if configuracion is not None:
        organizacion_id = getattr(
            configuracion,
            "organizacion_id",
            None,
        )
        if organizacion_id:
            return int(organizacion_id)

    return int(organizacion_id_predeterminada)


def asegurar_evento_fiscal_tenant(
    *,
    db,
    inspect_fn,
    text_fn,
    EventoFiscal,
    organizacion_id_predeterminada,
    logger_fn=print,
):
    """
    Agrega organizacion_id si la tabla fiscal fue creada antes
    de incorporar aislamiento tenant.
    """
    inspector = inspect_fn(db.engine)
    columnas = {
        columna["name"]
        for columna in inspector.get_columns(
            "evento_fiscal"
        )
    }

    columna_creada = False

    if "organizacion_id" not in columnas:
        db.session.execute(text_fn(
            "ALTER TABLE evento_fiscal "
            "ADD COLUMN organizacion_id INTEGER"
        ))
        db.session.commit()
        columna_creada = True

    db.session.execute(text_fn(
        "CREATE INDEX IF NOT EXISTS "
        "ix_evento_fiscal_organizacion_id "
        "ON evento_fiscal (organizacion_id)"
    ))
    db.session.commit()

    pendientes = (
        EventoFiscal.query
        .filter(
            EventoFiscal.organizacion_id.is_(None)
        )
        .all()
    )

    for evento in pendientes:
        evento.organizacion_id = (
            organizacion_evento_legacy(
                evento,
                organizacion_id_predeterminada,
            )
        )

    if pendientes:
        db.session.commit()

    if (
        logger_fn is not None
        and (columna_creada or pendientes)
    ):
        logger_fn(
            "[SAAS] Eventos fiscales asociados "
            "a una organizacion."
        )

    return {
        "columna_creada": columna_creada,
        "eventos_actualizados": len(pendientes),
    }


def organizacion_movimiento_legacy(
    movimiento,
    organizacion_id_predeterminada,
):
    existencia = getattr(
        movimiento,
        "existencia",
        None,
    )

    if existencia is not None:
        organizacion_id = getattr(
            existencia,
            "organizacion_id",
            None,
        )

        if organizacion_id:
            return int(organizacion_id)

    return int(organizacion_id_predeterminada)


def asegurar_movimiento_inventario_tenant(
    *,
    db,
    inspect_fn,
    text_fn,
    MovimientoInventario,
    organizacion_id_predeterminada,
    logger_fn=print,
):
    """
    Incorpora organizacion_id a movimientos legacy.

    La migracion es aditiva: no elimina ni renombra
    columnas y no genera movimientos de stock.
    """
    inspector = inspect_fn(db.engine)
    columnas = {
        columna["name"]
        for columna in inspector.get_columns(
            "movimiento_inventario"
        )
    }

    columna_creada = False

    if "organizacion_id" not in columnas:
        db.session.execute(text_fn(
            "ALTER TABLE movimiento_inventario "
            "ADD COLUMN organizacion_id INTEGER"
        ))
        db.session.commit()
        columna_creada = True

    db.session.execute(text_fn(
        "CREATE INDEX IF NOT EXISTS "
        "ix_movimiento_inventario_organizacion_id "
        "ON movimiento_inventario "
        "(organizacion_id)"
    ))
    db.session.commit()

    pendientes = (
        MovimientoInventario.query
        .filter(
            MovimientoInventario
            .organizacion_id
            .is_(None)
        )
        .all()
    )

    for movimiento in pendientes:
        movimiento.organizacion_id = (
            organizacion_movimiento_legacy(
                movimiento,
                organizacion_id_predeterminada,
            )
        )

    if pendientes:
        db.session.commit()

    if (
        logger_fn is not None
        and (columna_creada or pendientes)
    ):
        logger_fn(
            "[SAAS] Movimientos de inventario "
            "asociados a una organizacion."
        )

    return {
        "columna_creada": columna_creada,
        "movimientos_actualizados": len(
            pendientes
        ),
    }


def organizacion_identidad_canal_legacy(
    identidad,
    organizacion_id_predeterminada,
):
    cliente = getattr(
        identidad,
        "cliente",
        None,
    )

    if cliente is not None:
        organizacion_id = getattr(
            cliente,
            "organizacion_id",
            None,
        )

        if organizacion_id:
            return int(organizacion_id)

    return int(organizacion_id_predeterminada)


def asegurar_identidad_canal_crm_tenant(
    *,
    db,
    inspect_fn,
    text_fn,
    ClienteIdentidadCanal,
    organizacion_id_predeterminada,
    logger_fn=print,
):
    """
    Agrega tenant explicito a identidades CRM legacy.

    No importa clientes desde canales ni activa
    sincronizaciones o automatizaciones.
    """
    inspector = inspect_fn(db.engine)
    columnas = {
        columna["name"]
        for columna in inspector.get_columns(
            "cliente_identidad_canal"
        )
    }

    columna_creada = False

    if "organizacion_id" not in columnas:
        db.session.execute(text_fn(
            "ALTER TABLE cliente_identidad_canal "
            "ADD COLUMN organizacion_id INTEGER"
        ))
        db.session.commit()
        columna_creada = True

    db.session.execute(text_fn(
        "CREATE INDEX IF NOT EXISTS "
        "ix_cliente_identidad_canal_"
        "organizacion_id "
        "ON cliente_identidad_canal "
        "(organizacion_id)"
    ))
    db.session.commit()

    pendientes = (
        ClienteIdentidadCanal.query
        .filter(
            ClienteIdentidadCanal
            .organizacion_id
            .is_(None)
        )
        .all()
    )

    for identidad in pendientes:
        identidad.organizacion_id = (
            organizacion_identidad_canal_legacy(
                identidad,
                organizacion_id_predeterminada,
            )
        )

    if pendientes:
        db.session.commit()

    if (
        logger_fn is not None
        and (columna_creada or pendientes)
    ):
        logger_fn(
            "[SAAS] Identidades CRM asociadas "
            "a una organizacion."
        )

    return {
        "columna_creada": columna_creada,
        "identidades_actualizadas": len(
            pendientes
        ),
    }
