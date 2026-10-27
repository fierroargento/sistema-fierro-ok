"""
Consultas tenant del panel administrativo CRM.

No importa pedidos, no consulta APIs y no ejecuta
mensajes o automatizaciones.
"""


def obtener_datos_panel_crm(
    organizacion_id,
    *,
    modelos,
    unidad_negocio_id=None,
    db_session=None,
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
    LoteImportacionCRM = modelos.get("LoteImportacionCRM")

    if unidad_negocio_id is not None:
        from services.clientes_unidad import consulta
        from scripts.preparar_clientes_unidad import preparado
        from models.cliente_unidad import ClienteUnidad
        if db_session is None:
            from extensions import db
            db_session=db.session
        listo=preparado(db_session.connection())
        clientes=consulta(ClienteCRM,organizacion_id,unidad_negocio_id,db_session).order_by(ClienteCRM.nombre).all()
        ids=[c.id for c in clientes]
        filtros=dict(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id)
        identidades=ClienteIdentidadCanal.query.filter_by(**filtros).filter(ClienteIdentidadCanal.cliente_crm_id.in_(ids)).all() if listo else []
        oportunidades=OportunidadCRM.query.filter_by(**filtros).filter(OportunidadCRM.cliente_crm_id.in_(ids)).order_by(OportunidadCRM.id.desc()).all()
        actividades=ActividadCRM.query.filter_by(**filtros).filter(ActividadCRM.cliente_crm_id.in_(ids)).order_by(ActividadCRM.id.desc()).all() if listo else []
        lotes=LoteImportacionCRM.query.filter_by(**filtros).order_by(LoteImportacionCRM.id.desc()).limit(50).all() if listo and LoteImportacionCRM else []
        activos={v.cliente_id:v.activo for v in db_session.query(ClienteUnidad).filter_by(**filtros).all()} if listo else {}
        return dict(modulo_crm=ModuloOrganizacion.query.filter_by(organizacion_id=organizacion_id,codigo='crm').first(),
            unidades=UnidadNegocio.query.filter_by(id=unidad_negocio_id,organizacion_id=organizacion_id).all(),
            etapas=EtapaCRM.query.filter_by(organizacion_id=organizacion_id).order_by(EtapaCRM.orden).all(),
            clientes=clientes,identidades=identidades,oportunidades=oportunidades,actividades=actividades,lotes_importacion=lotes,
            clientes_unidad_preparados=listo,clientes_activos_unidad=activos,unidad_crm_id=unidad_negocio_id)

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

    lotes_importacion = [] if LoteImportacionCRM is None else (
        LoteImportacionCRM.query
        .filter(LoteImportacionCRM.organizacion_id == organizacion_id)
        .order_by(LoteImportacionCRM.id.desc())
        .limit(50)
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
        "lotes_importacion": lotes_importacion,
    }
