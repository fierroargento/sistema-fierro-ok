"""
Inicializacion ordenada de la base SaaS.
"""


def inicializar_base_datos_saas(
    app,
    *,
    dependencias,
):
    from services.estructura_empresarial import (
        asegurar_estructura_empresarial_inicial,
    )
    from services.migraciones_saas import (
        asegurar_codigos_unicos_por_tenant,
        asegurar_evento_fiscal_tenant,
        asegurar_identidad_canal_crm_tenant,
        asegurar_movimiento_inventario_tenant,
        asegurar_periodicidad_costos_fijos,
        asegurar_reglas_ajuste_configurables,
        asegurar_obligaciones_ajustables,
        asegurar_recursos_mano_obra,
        asegurar_unidad_importacion_costos,
    )
    from services.modulos_organizacion import (
        asegurar_modulos_iniciales,
    )
    from services.productos_catalogo_db import (
        asegurar_columnas_producto_logistica,
    )
    from services.tenant_context import (
        asegurar_membresias_organizacion_inicial,
    )

    db = dependencias["db"]
    modelos = dependencias["modelos"]
    inspect_fn = dependencias["inspect"]
    text_fn = dependencias["text"]
    logger_fn = dependencias.get(
        "logger_fn",
        print,
    )

    with app.app_context():
        db.create_all()

        asegurar_unidad_importacion_costos(
            db=db, inspect_fn=inspect_fn, text_fn=text_fn, logger_fn=logger_fn,
        )

        asegurar_recursos_mano_obra(
            db=db, inspect_fn=inspect_fn, text_fn=text_fn, logger_fn=logger_fn,
        )

        asegurar_periodicidad_costos_fijos(
            db=db, inspect_fn=inspect_fn, text_fn=text_fn, logger_fn=logger_fn,
        )

        asegurar_reglas_ajuste_configurables(
            db=db, inspect_fn=inspect_fn, text_fn=text_fn, logger_fn=logger_fn,
        )

        asegurar_obligaciones_ajustables(
            db=db, inspect_fn=inspect_fn, text_fn=text_fn, logger_fn=logger_fn,
        )

        from services.cuentas_pagar_productivas import asegurar_obligacion_ajuste
        for regla in modelos["ReglaAjusteIPCProductivo"].query.filter_by(activa=True).all():
            asegurar_obligacion_ajuste(
                regla,
                ObligacionCostoProductivo=modelos["ObligacionCostoProductivo"],
                CostoFijoVersion=modelos["CostoFijoVersion"], db_session=db.session,
            )

        estructura_inicial = (
            asegurar_estructura_empresarial_inicial(
                Organizacion=(
                    modelos["Organizacion"]
                ),
                UnidadNegocio=(
                    modelos["UnidadNegocio"]
                ),
                db_session=db.session,
                logger_fn=logger_fn,
            )
        )

        organizacion_id = estructura_inicial[
            "organizacion"
        ].id

        asegurar_evento_fiscal_tenant(
            db=db,
            inspect_fn=inspect_fn,
            text_fn=text_fn,
            EventoFiscal=modelos["EventoFiscal"],
            organizacion_id_predeterminada=(
                organizacion_id
            ),
            logger_fn=logger_fn,
        )

        asegurar_movimiento_inventario_tenant(
            db=db,
            inspect_fn=inspect_fn,
            text_fn=text_fn,
            MovimientoInventario=(
                modelos["MovimientoInventario"]
            ),
            organizacion_id_predeterminada=(
                organizacion_id
            ),
            logger_fn=logger_fn,
        )

        asegurar_identidad_canal_crm_tenant(
            db=db,
            inspect_fn=inspect_fn,
            text_fn=text_fn,
            ClienteIdentidadCanal=(
                modelos["ClienteIdentidadCanal"]
            ),
            organizacion_id_predeterminada=(
                organizacion_id
            ),
            logger_fn=logger_fn,
        )

        asegurar_codigos_unicos_por_tenant(
            db=db,
            inspect_fn=inspect_fn,
            text_fn=text_fn,
            logger_fn=logger_fn,
        )

        asegurar_modulos_iniciales(
            ModuloOrganizacion=(
                modelos["ModuloOrganizacion"]
            ),
            organizacion_id=organizacion_id,
            db_session=db.session,
            logger_fn=logger_fn,
        )

        for nombre in (
            "asegurar_columnas_extra",
            "asegurar_columnas_integracion_ml",
            "backfill_ml_identidad_cuenta_pedidos",
            "asegurar_columnas_integracion_tn",
        ):
            dependencias[nombre]()

        asegurar_columnas_producto_logistica(
            db,
            inspect_fn,
            text_fn,
        )

        dependencias[
            "asegurar_usuarios_iniciales"
        ]()

        asegurar_membresias_organizacion_inicial(
            UsuarioSistema=(
                modelos["UsuarioSistema"]
            ),
            UsuarioOrganizacion=(
                modelos["UsuarioOrganizacion"]
            ),
            organizacion_id=organizacion_id,
            db_session=db.session,
            logger_fn=logger_fn,
        )

        dependencias[
            "asegurar_configuracion_inicial"
        ]()
