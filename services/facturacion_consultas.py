"""
Consultas tenant-safe para el panel fiscal.
"""


def obtener_datos_panel_facturacion(
    *,
    organizacion_id,
    modelos,
):
    ModuloOrganizacion = modelos[
        "ModuloOrganizacion"
    ]
    EntidadFiscal = modelos["EntidadFiscal"]
    ConfiguracionFiscal = modelos[
        "ConfiguracionFiscal"
    ]
    PuntoVentaFiscal = modelos[
        "PuntoVentaFiscal"
    ]
    TipoComprobanteFiscal = modelos[
        "TipoComprobanteFiscal"
    ]
    ClienteCRM = modelos["ClienteCRM"]
    BorradorComprobanteFiscal = modelos[
        "BorradorComprobanteFiscal"
    ]
    EventoFiscal = modelos["EventoFiscal"]

    modulo = (
        ModuloOrganizacion.query
        .filter_by(
            organizacion_id=organizacion_id,
            codigo="facturacion-multicuit",
        )
        .first()
    )
    entidades = (
        EntidadFiscal.query
        .filter_by(
            organizacion_id=organizacion_id
        )
        .order_by(
            EntidadFiscal.razon_social.asc()
        )
        .all()
    )
    configuraciones = (
        ConfiguracionFiscal.query
        .filter_by(
            organizacion_id=organizacion_id
        )
        .order_by(
            ConfiguracionFiscal.id.asc()
        )
        .all()
    )
    puntos = (
        PuntoVentaFiscal.query
        .filter_by(
            organizacion_id=organizacion_id
        )
        .order_by(
            PuntoVentaFiscal.numero.asc()
        )
        .all()
    )
    tipos = (
        TipoComprobanteFiscal.query
        .join(PuntoVentaFiscal)
        .filter(
            PuntoVentaFiscal.organizacion_id
            == organizacion_id
        )
        .order_by(
            TipoComprobanteFiscal.id.asc()
        )
        .all()
    )
    clientes = (
        ClienteCRM.query
        .filter_by(
            organizacion_id=organizacion_id
        )
        .order_by(
            ClienteCRM.nombre.asc()
        )
        .all()
    )
    borradores = (
        BorradorComprobanteFiscal.query
        .filter_by(
            organizacion_id=organizacion_id
        )
        .order_by(
            BorradorComprobanteFiscal.id.desc()
        )
        .all()
    )
    eventos = (
        EventoFiscal.query
        .filter_by(
            organizacion_id=organizacion_id
        )
        .order_by(
            EventoFiscal.id.desc()
        )
        .limit(200)
        .all()
    )

    return {
        "modulo_facturacion": modulo,
        "entidades_fiscales": entidades,
        "configuraciones": configuraciones,
        "puntos_venta": puntos,
        "tipos_comprobante": tipos,
        "clientes_crm": clientes,
        "borradores": borradores,
        "eventos": eventos,
    }
