"""
Migraciones aditivas para la transicion SaaS.

No elimina columnas ni modifica flujos operativos.
"""


def asegurar_ficha_catalogo_integral(*, db, inspect_fn, text_fn, logger_fn=print):
    """Amplía CatalogoProducto conservando las inclusiones existentes."""
    inspector = inspect_fn(db.engine)
    tabla = "catalogo_producto"
    if tabla not in inspector.get_table_names():
        return {"columnas_creadas": []}
    columnas = {columna["name"] for columna in inspector.get_columns(tabla)}
    definiciones = {
        "marca": "VARCHAR(120)",
        "categoria": "VARCHAR(120)",
        "descripcion_corta": "VARCHAR(300)",
        "descripcion_publica": "TEXT",
        "estado_comercial": "VARCHAR(20) NOT NULL DEFAULT 'borrador'",
        "estado_disponibilidad": "VARCHAR(20) NOT NULL DEFAULT 'no_disponible'",
        "motivo_disponibilidad": "VARCHAR(300)",
        "material": "VARCHAR(120)",
        "color": "VARCHAR(120)",
        "terminacion": "VARCHAR(120)",
        "contenido_paquete": "TEXT",
        "peso_producto_gr": "NUMERIC(12, 3)",
        "largo_producto_cm": "NUMERIC(12, 3)",
        "ancho_producto_cm": "NUMERIC(12, 3)",
        "alto_producto_cm": "NUMERIC(12, 3)",
        "atributos_json": "TEXT NOT NULL DEFAULT '{}'",
        "variantes_json": "TEXT NOT NULL DEFAULT '[]'",
        "imagenes_json": "TEXT NOT NULL DEFAULT '[]'",
        "canales_json": "TEXT NOT NULL DEFAULT '{}'",
        "relaciones_json": "TEXT NOT NULL DEFAULT '[]'",
        "completitud_pct": "INTEGER NOT NULL DEFAULT 0",
        "faltantes_ficha": "TEXT",
    }
    creadas = []
    for nombre, definicion in definiciones.items():
        if nombre not in columnas:
            db.session.execute(text_fn(
                f"ALTER TABLE {tabla} ADD COLUMN {nombre} {definicion}"
            ))
            creadas.append(nombre)
    if "estado_comercial" in creadas:
        db.session.execute(text_fn(
            "UPDATE catalogo_producto SET estado_comercial = "
            "CASE WHEN activo = TRUE THEN 'activo' ELSE 'borrador' END"
        ))
    if "estado_disponibilidad" in creadas:
        db.session.execute(text_fn(
            "UPDATE catalogo_producto SET estado_disponibilidad = "
            "CASE WHEN disponible = TRUE THEN 'disponible' ELSE 'no_disponible' END"
        ))
    db.session.execute(text_fn(
        "CREATE INDEX IF NOT EXISTS ix_catalogo_producto_estado_comercial "
        "ON catalogo_producto (estado_comercial)"
    ))
    db.session.execute(text_fn(
        "CREATE INDEX IF NOT EXISTS ix_catalogo_producto_estado_disponibilidad "
        "ON catalogo_producto (estado_disponibilidad)"
    ))
    db.session.commit()
    if creadas and logger_fn is not None:
        logger_fn("[SAAS] Ficha integral de productos de catálogo habilitada.")
    return {"columnas_creadas": creadas}


def asegurar_recursos_mano_obra(*, db, inspect_fn, text_fn, logger_fn=print):
    """Completa el maestro laboral legacy sin alterar empleados existentes."""
    inspector = inspect_fn(db.engine)
    if "empleado_productivo" not in inspector.get_table_names():
        return {"columnas_creadas": []}
    columnas = {
        columna["name"]
        for columna in inspector.get_columns("empleado_productivo")
    }
    creadas = []
    if "tipo_registro" not in columnas:
        db.session.execute(text_fn(
            "ALTER TABLE empleado_productivo "
            "ADD COLUMN tipo_registro VARCHAR(20) NOT NULL DEFAULT 'empleado'"
        ))
        creadas.append("tipo_registro")
    if "porcentaje_indirecto" not in columnas:
        db.session.execute(text_fn(
            "ALTER TABLE empleado_productivo "
            "ADD COLUMN porcentaje_indirecto NUMERIC(9, 4) NOT NULL DEFAULT 0"
        ))
        creadas.append("porcentaje_indirecto")
    db.session.execute(text_fn(
        "CREATE INDEX IF NOT EXISTS ix_empleado_productivo_tipo_registro "
        "ON empleado_productivo (tipo_registro)"
    ))
    db.session.commit()
    inspector = inspect_fn(db.engine)
    if "empleado_costo_version" in inspector.get_table_names():
        columnas_version = {
            columna["name"]
            for columna in inspector.get_columns("empleado_costo_version")
        }
        if "porcentaje_cargas" not in columnas_version:
            db.session.execute(text_fn(
                "ALTER TABLE empleado_costo_version "
                "ADD COLUMN porcentaje_cargas NUMERIC(9, 4) NOT NULL DEFAULT 0"
            ))
            creadas.append("porcentaje_cargas")
        if "usa_porcentaje_general" not in columnas_version:
            db.session.execute(text_fn(
                "ALTER TABLE empleado_costo_version "
                "ADD COLUMN usa_porcentaje_general BOOLEAN NOT NULL DEFAULT FALSE"
            ))
            creadas.append("usa_porcentaje_general")
        if "ubicacion_trabajo" not in columnas_version:
            db.session.execute(text_fn(
                "ALTER TABLE empleado_costo_version ADD COLUMN ubicacion_trabajo "
                "VARCHAR(120) NOT NULL DEFAULT 'Sin definir'"
            ))
            creadas.append("ubicacion_trabajo")
        if "tipo_funcion" not in columnas_version:
            db.session.execute(text_fn(
                "ALTER TABLE empleado_costo_version ADD COLUMN tipo_funcion "
                "VARCHAR(30) NOT NULL DEFAULT 'directa'"
            ))
            creadas.append("tipo_funcion")
        if "porcentaje_productivo" not in columnas_version:
            db.session.execute(text_fn(
                "ALTER TABLE empleado_costo_version ADD COLUMN porcentaje_productivo "
                "NUMERIC(9, 4) NOT NULL DEFAULT 100"
            ))
            creadas.append("porcentaje_productivo")
        db.session.commit()
    if creadas and logger_fn is not None:
        logger_fn("[SAAS] Recursos productivos habilitados en mano de obra.")
    return {"columnas_creadas": creadas}


def asegurar_periodicidad_costos_fijos(*, db, inspect_fn, text_fn, logger_fn=print):
    """Agrega metadatos aditivos y conserva importes mensuales históricos."""
    inspector = inspect_fn(db.engine)
    if "costo_fijo_version" not in inspector.get_table_names():
        return {"columnas_creadas": []}
    columnas = {columna["name"] for columna in inspector.get_columns("costo_fijo_version")}
    definiciones = {
        "importe_periodo_centavos": "BIGINT NOT NULL DEFAULT 0",
        "naturaleza": "VARCHAR(20) NOT NULL DEFAULT 'fijo'",
        "periodicidad": "VARCHAR(20) NOT NULL DEFAULT 'mensual'",
        "meses_cobertura": "NUMERIC(9, 2) NOT NULL DEFAULT 1",
    }
    creadas = []
    for nombre, definicion in definiciones.items():
        if nombre not in columnas:
            db.session.execute(text_fn(
                f"ALTER TABLE costo_fijo_version ADD COLUMN {nombre} {definicion}"
            ))
            creadas.append(nombre)
    if "importe_periodo_centavos" in creadas:
        db.session.execute(text_fn(
            "UPDATE costo_fijo_version SET importe_periodo_centavos = "
            "importe_mensual_centavos WHERE importe_periodo_centavos = 0"
        ))
    db.session.commit()
    if creadas and logger_fn is not None:
        logger_fn("[SAAS] Periodicidad de costos fijos habilitada.")
    return {"columnas_creadas": creadas}


def asegurar_reglas_ajuste_configurables(*, db, inspect_fn, text_fn, logger_fn=print):
    """Amplía las reglas IPC existentes sin activar ni modificar configuraciones."""
    inspector = inspect_fn(db.engine)
    tabla = "regla_ajuste_ipc_productivo"
    if tabla not in inspector.get_table_names():
        return {"columnas_creadas": []}
    columnas = {columna["name"] for columna in inspector.get_columns(tabla)}
    definiciones = {
        "tipo_ajuste": "VARCHAR(30) NOT NULL DEFAULT 'ipc'",
        "periodo_ipc_inicio": "DATE",
        "periodo_ipc_final": "DATE",
        "modalidad_pago": "VARCHAR(20) NOT NULL DEFAULT 'adelantado'",
        "requiere_aprobacion": "BOOLEAN NOT NULL DEFAULT TRUE",
    }
    creadas = []
    for nombre, definicion in definiciones.items():
        if nombre not in columnas:
            db.session.execute(text_fn(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {definicion}"))
            creadas.append(nombre)
    db.session.commit()
    if creadas and logger_fn is not None:
        logger_fn("[SAAS] Reglas configurables de ajuste habilitadas.")
    return {"columnas_creadas": creadas}


def asegurar_obligaciones_ajustables(*, db, inspect_fn, text_fn, logger_fn=print):
    """Vincula obligaciones con reglas y propuestas sin alterar pagos existentes."""
    inspector = inspect_fn(db.engine)
    tabla = "obligacion_costo_productivo"
    if tabla not in inspector.get_table_names():
        return {"columnas_creadas": []}
    columnas = {columna["name"] for columna in inspector.get_columns(tabla)}
    definiciones = {
        "regla_ajuste_id": "INTEGER",
        "propuesta_ajuste_id": "INTEGER",
        "ajuste_pendiente": "BOOLEAN NOT NULL DEFAULT FALSE",
    }
    creadas = []
    for nombre, definicion in definiciones.items():
        if nombre not in columnas:
            db.session.execute(text_fn(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {definicion}"))
            creadas.append(nombre)
    db.session.execute(text_fn(
        "CREATE INDEX IF NOT EXISTS ix_obligacion_costo_ajuste_pendiente "
        "ON obligacion_costo_productivo (ajuste_pendiente)"
    ))
    db.session.commit()
    if creadas and logger_fn is not None:
        logger_fn("[SAAS] Obligaciones pendientes de ajuste habilitadas.")
    return {"columnas_creadas": creadas}


def asegurar_auditoria_pagos_productivos(*, db, inspect_fn, text_fn, logger_fn=print):
    """Amplía pagos existentes sin borrar ni reinterpretar movimientos previos."""
    inspector = inspect_fn(db.engine)
    tabla = "pago_obligacion_costo_productivo"
    if tabla not in inspector.get_table_names():
        return {"columnas_creadas": []}
    columnas = {columna["name"] for columna in inspector.get_columns(tabla)}
    definiciones = {
        "comprobante": "VARCHAR(500)",
        "anulado": "BOOLEAN NOT NULL DEFAULT FALSE",
        "motivo_anulacion": "VARCHAR(500)",
        "fecha_anulacion": "TIMESTAMP",
        "anulado_por_usuario_id": "INTEGER",
    }
    creadas = []
    for nombre, definicion in definiciones.items():
        if nombre not in columnas:
            db.session.execute(text_fn(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {definicion}"))
            creadas.append(nombre)
    db.session.execute(text_fn(
        "CREATE INDEX IF NOT EXISTS ix_pago_obligacion_anulado "
        "ON pago_obligacion_costo_productivo (anulado)"
    ))
    db.session.commit()
    if creadas and logger_fn is not None:
        logger_fn("[SAAS] Auditoría de pagos productivos habilitada.")
    return {"columnas_creadas": creadas}


def asegurar_unidad_importacion_costos(*, db, inspect_fn, text_fn, logger_fn=print):
    """Agrega alcance por unidad a lotes comerciales sin alterar lotes previos."""
    inspector = inspect_fn(db.engine)
    if "importacion_masiva_costo" not in inspector.get_table_names():
        return {"columna_creada": False}
    columnas = {
        columna["name"]
        for columna in inspector.get_columns("importacion_masiva_costo")
    }
    creada = "unidad_negocio_id" not in columnas
    if creada:
        db.session.execute(text_fn(
            "ALTER TABLE importacion_masiva_costo "
            "ADD COLUMN unidad_negocio_id INTEGER"
        ))
        db.session.commit()
    db.session.execute(text_fn(
        "CREATE INDEX IF NOT EXISTS ix_importacion_masiva_costo_unidad_negocio_id "
        "ON importacion_masiva_costo (unidad_negocio_id)"
    ))
    db.session.commit()
    if creada and logger_fn is not None:
        logger_fn("[SAAS] Importaciones comerciales aisladas por unidad.")
    return {"columna_creada": creada}


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


def especificaciones_codigos_tenant():
    return (
        (
            "catalogo",
            "uq_catalogo_organizacion_codigo",
        ),
        (
            "cliente_crm",
            "uq_cliente_crm_organizacion_codigo",
        ),
        (
            "etapa_crm",
            "uq_etapa_crm_organizacion_codigo",
        ),
        (
            "unidad_negocio",
            "uq_unidad_negocio_organizacion_codigo",
        ),
        (
            "sucursal_operativa",
            "uq_sucursal_operativa_organizacion_codigo",
        ),
        (
            "entidad_fiscal",
            "uq_entidad_fiscal_organizacion_codigo",
        ),
        (
            "modulo_organizacion",
            "uq_modulo_organizacion_codigo",
        ),
    )


def _columnas_constraint(constraint):
    return tuple(
        constraint.get("column_names")
        or ()
    )


def asegurar_codigos_unicos_por_tenant(
    *,
    db,
    inspect_fn,
    text_fn,
    logger_fn=print,
):
    """
    Convierte unicidades globales de codigo en tenant.

    PostgreSQL permite retirar el constraint legacy.
    SQLite legacy conserva la restriccion global para
    evitar reconstruir tablas automaticamente.
    """
    dialecto = str(
        db.engine.dialect.name
        or ""
    ).lower()
    preparador = (
        db.engine.dialect.identifier_preparer
    )
    resultados = []

    for tabla, nombre_compuesto in (
        especificaciones_codigos_tenant()
    ):
        inspector = inspect_fn(db.engine)
        restricciones = (
            inspector.get_unique_constraints(
                tabla
            )
            or []
        )
        indices = (
            inspector.get_indexes(tabla)
            or []
        )

        globales = [
            restriccion
            for restriccion in restricciones
            if _columnas_constraint(
                restriccion
            ) == ("codigo",)
        ]

        compuesto_existe = any(
            _columnas_constraint(
                restriccion
            )
            == (
                "organizacion_id",
                "codigo",
            )
            for restriccion in restricciones
        ) or any(
            tuple(
                indice.get("column_names")
                or ()
            )
            == (
                "organizacion_id",
                "codigo",
            )
            and bool(
                indice.get("unique")
            )
            for indice in indices
        )

        global_retirado = False
        global_pendiente = False

        if not compuesto_existe:
            tabla_sql = preparador.quote(tabla)
            indice_sql = preparador.quote(
                nombre_compuesto
            )
            organizacion_sql = preparador.quote(
                "organizacion_id"
            )
            codigo_sql = preparador.quote(
                "codigo"
            )

            db.session.execute(text_fn(
                f"CREATE UNIQUE INDEX IF NOT EXISTS "
                f"{indice_sql} ON {tabla_sql} "
                f"({organizacion_sql}, {codigo_sql})"
            ))
            db.session.commit()

        if globales and dialecto == "postgresql":
            tabla_sql = preparador.quote(tabla)

            for restriccion in globales:
                nombre = restriccion.get(
                    "name"
                )

                if not nombre:
                    raise RuntimeError(
                        "Constraint global sin nombre "
                        f"en {tabla}."
                    )

                nombre_sql = preparador.quote(
                    nombre
                )

                db.session.execute(text_fn(
                    f"ALTER TABLE {tabla_sql} "
                    f"DROP CONSTRAINT {nombre_sql}"
                ))

            db.session.commit()
            global_retirado = True

        elif globales:
            global_pendiente = True

        resultado = {
            "tabla": tabla,
            "global_retirado": global_retirado,
            "global_pendiente": global_pendiente,
            "compuesto_creado": (
                not compuesto_existe
            ),
        }
        resultados.append(resultado)

        if (
            logger_fn is not None
            and (
                global_retirado
                or global_pendiente
                or not compuesto_existe
            )
        ):
            detalle = (
                "constraint global retirado"
                if global_retirado
                else (
                    "constraint global legacy "
                    "conservado"
                    if global_pendiente
                    else "sin constraint global"
                )
            )

            logger_fn(
                f"[SAAS] {tabla}: unicidad tenant; "
                f"{detalle}."
            )

    return resultados
