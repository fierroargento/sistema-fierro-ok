"""
Consultas tenant del panel administrativo CRM.

No importa pedidos, no consulta APIs y no ejecuta
mensajes o automatizaciones.
"""


def obtener_datos_panel_crm(
    organizacion_id,
    *,
    modelos,
):
    organizacion_id = int(
        organizacion_id
    )

    ModuloOrganizacion = modelos[
        "ModuloOrganizacion"
    ]
    UnidadNegocio = modelos[
        "UnidadNegocio"
    ]
    ClienteCRM = modelos["ClienteCRM"]
    ClienteIdentidadCanal = modelos[
        "ClienteIdentidadCanal"
    ]
    EtapaCRM = modelos["EtapaCRM"]
    OportunidadCRM = modelos[
        "OportunidadCRM"
    ]
    ActividadCRM = modelos["ActividadCRM"]

    modulo_crm = (
        ModuloOrganizacion.query
        .filter_by(
            organizacion_id=organizacion_id,
            codigo="crm",
        )
        .first()
    )

    unidades = (
        UnidadNegocio.query
        .filter_by(
            organizacion_id=organizacion_id
        )
        .order_by(
            UnidadNegocio.nombre.asc()
        )
        .all()
    )

    etapas = (
        EtapaCRM.query
        .filter_by(
            organizacion_id=organizacion_id
        )
        .order_by(
            EtapaCRM.orden.asc(),
            EtapaCRM.nombre.asc(),
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

    identidades = (
        ClienteIdentidadCanal.query
        .filter_by(
            organizacion_id=organizacion_id
        )
        .order_by(
            ClienteIdentidadCanal.id.asc()
        )
        .all()
    )

    oportunidades = (
        OportunidadCRM.query
        .filter_by(
            organizacion_id=organizacion_id
        )
        .order_by(
            OportunidadCRM.id.desc()
        )
        .all()
    )

    actividades = (
        ActividadCRM.query
        .filter_by(
            organizacion_id=organizacion_id
        )
        .order_by(
            ActividadCRM.id.desc()
        )
        .all()
    )

    return {
        "modulo_crm": modulo_crm,
        "unidades": unidades,
        "etapas": etapas,
        "clientes": clientes,
        "identidades": identidades,
        "oportunidades": oportunidades,
        "actividades": actividades,
    }
