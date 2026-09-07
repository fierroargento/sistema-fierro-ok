"""Flujo interno explícito para asignar mensajes WhatsApp históricos."""

from services.fechas import ahora_utc_naive


def _guardar(db_session, commit):
    try:
        db_session.commit() if commit else db_session.flush()
    except Exception:
        db_session.rollback()
        raise


def preparar_propuestas_whatsapp(
    organizacion_id, *, WhatsAppMensaje, Pedido, AsignacionTenantWhatsApp,
    db_session, usuario, commit=True,
):
    pedidos = {p.id: p for p in Pedido.query.filter_by(organizacion_id=int(organizacion_id)).all()}
    creadas = 0
    for mensaje in WhatsAppMensaje.query.filter(WhatsAppMensaje.organizacion_id.is_(None)).yield_per(500):
        pedido = pedidos.get(getattr(mensaje, "pedido_id", None))
        if pedido is None or getattr(pedido, "unidad_negocio_id", None) is None:
            continue
        abierta = AsignacionTenantWhatsApp.query.filter_by(
            mensaje_id=mensaje.id, organizacion_id=int(organizacion_id),
        ).filter(AsignacionTenantWhatsApp.estado.in_(("preparada", "aprobada"))).first()
        if abierta is not None:
            continue
        propuesta = AsignacionTenantWhatsApp(
            mensaje_id=mensaje.id,
            pedido_id_snapshot=mensaje.pedido_id,
            organizacion_id=int(organizacion_id),
            unidad_negocio_id=pedido.unidad_negocio_id,
            estado="preparada",
            motivo="Candidato único por pedido ya aislado.",
            creado_por_username=getattr(usuario, "username", None),
        )
        db_session.add(propuesta)
        creadas += 1
    _guardar(db_session, commit)
    return creadas


def _propuesta(propuesta_id, organizacion_id, Modelo):
    propuesta = Modelo.query.filter_by(id=int(propuesta_id), organizacion_id=int(organizacion_id)).first()
    if propuesta is None:
        raise ValueError("La propuesta no pertenece a la organización.")
    return propuesta


def _revalidar(propuesta, *, WhatsAppMensaje, Pedido):
    mensaje = WhatsAppMensaje.query.filter_by(id=propuesta.mensaje_id).first()
    if mensaje is None or mensaje.organizacion_id is not None:
        raise ValueError("El mensaje ya no está disponible para asignación.")
    if mensaje.pedido_id != propuesta.pedido_id_snapshot:
        raise ValueError("El pedido asociado cambió; la propuesta quedó obsoleta.")
    pedido = Pedido.query.filter_by(
        id=mensaje.pedido_id, organizacion_id=propuesta.organizacion_id,
        unidad_negocio_id=propuesta.unidad_negocio_id,
    ).first()
    if pedido is None:
        raise ValueError("La identidad del pedido ya no coincide.")
    return mensaje


def aprobar_propuesta_whatsapp(
    propuesta_id, organizacion_id, *, WhatsAppMensaje, Pedido,
    AsignacionTenantWhatsApp, db_session, usuario, commit=True,
):
    propuesta = _propuesta(propuesta_id, organizacion_id, AsignacionTenantWhatsApp)
    if propuesta.estado != "preparada":
        raise ValueError("Solo se puede aprobar una propuesta preparada.")
    _revalidar(propuesta, WhatsAppMensaje=WhatsAppMensaje, Pedido=Pedido)
    propuesta.estado = "aprobada"
    propuesta.aprobado_por_username = getattr(usuario, "username", None)
    propuesta.fecha_aprobacion = ahora_utc_naive()
    _guardar(db_session, commit)
    return propuesta


def aplicar_propuesta_whatsapp(
    propuesta_id, organizacion_id, *, confirmacion, WhatsAppMensaje, Pedido,
    AsignacionTenantWhatsApp, db_session, usuario, commit=True,
):
    if str(confirmacion or "").strip().upper() != "ASIGNAR":
        raise ValueError("Escribí ASIGNAR para confirmar la aplicación.")
    propuesta = _propuesta(propuesta_id, organizacion_id, AsignacionTenantWhatsApp)
    if propuesta.estado != "aprobada":
        raise ValueError("La propuesta debe estar aprobada.")
    mensaje = _revalidar(propuesta, WhatsAppMensaje=WhatsAppMensaje, Pedido=Pedido)
    mensaje.organizacion_id = propuesta.organizacion_id
    mensaje.unidad_negocio_id = propuesta.unidad_negocio_id
    propuesta.estado = "aplicada"
    propuesta.aplicado_por_username = getattr(usuario, "username", None)
    propuesta.fecha_aplicacion = ahora_utc_naive()
    _guardar(db_session, commit)
    return propuesta
