"""Gestion auditable de proyecciones sin convertirlas en pagos o cobros."""

def cancelar_proyeccion(movimiento, *, organizacion_id, unidad_negocio_id, motivo, db_session):
    if int(movimiento.organizacion_id) != int(organizacion_id) or int(movimiento.unidad_negocio_id) != int(unidad_negocio_id):
        raise ValueError("La proyección no pertenece al contexto activo.")
    if movimiento.estado != "proyectado":
        raise ValueError("Solo puede cancelarse una proyección vigente.")
    if movimiento.confirmado or movimiento.afecta_saldo:
        raise ValueError("La proyección presenta un impacto incompatible con la etapa preparatoria.")
    motivo = str(motivo or "").strip()
    if len(motivo) < 5:
        raise ValueError("El motivo de cancelación debe ser explícito.")
    movimiento.estado = "cancelado"
    movimiento.observacion = f"Cancelada sin impacto: {motivo}"
    db_session.commit()
    return movimiento
