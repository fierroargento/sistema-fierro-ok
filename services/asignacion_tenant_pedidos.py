"""Flujo interno, auditable y explícito para asignar pedidos a un tenant."""

from services.fechas import ahora_utc_naive
from services.identidad_tenant_pedidos import (
    candidatos_pedido,
    construir_indices_vinculos,
)


ESTADOS_ABIERTOS = {"preparada", "aprobada"}


def _usuario(propuesta, prefijo, usuario):
    setattr(propuesta, f"{prefijo}_por_usuario_id", getattr(usuario, "id", None))
    setattr(
        propuesta,
        f"{prefijo}_por_username",
        str(getattr(usuario, "username", "") or "").strip() or None,
    )


def _guardar(db_session, commit):
    try:
        if commit:
            db_session.commit()
        else:
            db_session.flush()
    except Exception:
        db_session.rollback()
        raise


def preparar_propuestas_tenant(
    organizacion_id,
    *, Pedido, VinculoCanalComercial, AsignacionTenantPedido,
    db_session, usuario, commit=True,
):
    vinculos = VinculoCanalComercial.query.all()
    indices = construir_indices_vinculos(vinculos)
    creadas = 0
    pedidos = Pedido.query.filter(Pedido.organizacion_id.is_(None)).yield_per(500)
    for pedido in pedidos:
        candidatos = candidatos_pedido(pedido, indices)
        if len(candidatos) != 1:
            continue
        candidato = next(iter(candidatos))
        if candidato[0] != int(organizacion_id) or candidato[1] is None:
            continue
        abierta = AsignacionTenantPedido.query.filter(
            AsignacionTenantPedido.pedido_id == pedido.id,
            AsignacionTenantPedido.estado.in_(ESTADOS_ABIERTOS),
        ).first()
        if abierta is not None:
            continue
        propuesta = AsignacionTenantPedido(
            pedido_id=pedido.id,
            organizacion_id=candidato[0],
            unidad_negocio_id=candidato[1],
            estado="preparada",
            ml_cuenta_id_snapshot=getattr(pedido, "ml_cuenta_id", None),
            tn_cuenta_id_snapshot=getattr(pedido, "tn_cuenta_id", None),
            motivo="Candidato único por vínculo interno de cuenta.",
        )
        _usuario(propuesta, "creado", usuario)
        db_session.add(propuesta)
        creadas += 1
    _guardar(db_session, commit)
    return creadas


def _obtener_propuesta(
    propuesta_id, organizacion_id, *, AsignacionTenantPedido,
):
    propuesta = AsignacionTenantPedido.query.filter_by(
        id=int(propuesta_id), organizacion_id=int(organizacion_id),
    ).first()
    if propuesta is None:
        raise ValueError("La propuesta no pertenece a la organización.")
    return propuesta


def _revalidar(propuesta, *, Pedido, VinculoCanalComercial):
    pedido = Pedido.query.get(propuesta.pedido_id)
    if pedido is None:
        raise ValueError("El pedido ya no existe.")
    if pedido.organizacion_id is not None:
        raise ValueError("El pedido ya tiene una organización asignada.")
    if (
        pedido.ml_cuenta_id != propuesta.ml_cuenta_id_snapshot
        or pedido.tn_cuenta_id != propuesta.tn_cuenta_id_snapshot
    ):
        raise ValueError("Las cuentas del pedido cambiaron; la propuesta quedó obsoleta.")
    candidatos = candidatos_pedido(
        pedido,
        construir_indices_vinculos(VinculoCanalComercial.query.all()),
    )
    esperado = (propuesta.organizacion_id, propuesta.unidad_negocio_id)
    if candidatos != {esperado}:
        raise ValueError("La identidad candidata cambió; prepará una propuesta nueva.")
    return pedido


def aprobar_propuesta_tenant(
    propuesta_id, organizacion_id, *, Pedido, VinculoCanalComercial,
    AsignacionTenantPedido, db_session, usuario, commit=True,
):
    propuesta = _obtener_propuesta(
        propuesta_id, organizacion_id,
        AsignacionTenantPedido=AsignacionTenantPedido,
    )
    if propuesta.estado != "preparada":
        raise ValueError("Solo se puede aprobar una propuesta preparada.")
    _revalidar(propuesta, Pedido=Pedido, VinculoCanalComercial=VinculoCanalComercial)
    propuesta.estado = "aprobada"
    propuesta.fecha_aprobacion = ahora_utc_naive()
    _usuario(propuesta, "aprobado", usuario)
    _guardar(db_session, commit)
    return propuesta


def rechazar_propuesta_tenant(
    propuesta_id, organizacion_id, *, motivo, AsignacionTenantPedido,
    db_session, usuario, commit=True,
):
    propuesta = _obtener_propuesta(
        propuesta_id, organizacion_id,
        AsignacionTenantPedido=AsignacionTenantPedido,
    )
    if propuesta.estado not in ESTADOS_ABIERTOS:
        raise ValueError("La propuesta ya está cerrada.")
    propuesta.estado = "rechazada"
    propuesta.motivo = str(motivo or "").strip()[:500] or "Rechazada por operador."
    _usuario(propuesta, "rechazado", usuario)
    propuesta.fecha_rechazo = ahora_utc_naive()
    _guardar(db_session, commit)
    return propuesta


def aplicar_propuesta_tenant(
    propuesta_id, organizacion_id, *, confirmacion, Pedido,
    VinculoCanalComercial, AsignacionTenantPedido, db_session,
    usuario, commit=True,
):
    if str(confirmacion or "").strip().upper() != "ASIGNAR":
        raise ValueError("Escribí ASIGNAR para confirmar la aplicación.")
    propuesta = _obtener_propuesta(
        propuesta_id, organizacion_id,
        AsignacionTenantPedido=AsignacionTenantPedido,
    )
    if propuesta.estado != "aprobada":
        raise ValueError("La propuesta debe estar aprobada.")
    pedido = _revalidar(
        propuesta, Pedido=Pedido,
        VinculoCanalComercial=VinculoCanalComercial,
    )
    pedido.organizacion_id = propuesta.organizacion_id
    pedido.unidad_negocio_id = propuesta.unidad_negocio_id
    propuesta.estado = "aplicada"
    propuesta.fecha_aplicacion = ahora_utc_naive()
    _usuario(propuesta, "aplicado", usuario)
    _guardar(db_session, commit)
    return propuesta
