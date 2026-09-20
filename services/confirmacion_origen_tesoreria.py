"""Confirma un candidato interno como proyeccion; nunca como dinero real."""

from datetime import date


def confirmar_candidato(candidato, *, cuenta, organizacion_id, unidad_negocio_id,
                        Movimiento, db_session, usuario_id=None):
    if int(cuenta.organizacion_id) != int(organizacion_id) or int(cuenta.unidad_negocio_id) != int(unidad_negocio_id):
        raise ValueError("La cuenta no pertenece al contexto activo.")
    if candidato.get("ya_proyectado"):
        raise ValueError("El origen ya tiene una proyección equivalente.")
    if candidato.get("origen") not in {"obligacion_costo", "liquidacion_canal_esperada"}:
        raise ValueError("El origen interno no es confirmable.")
    if candidato.get("tipo") not in {"ingreso", "egreso"}:
        raise ValueError("El tipo de proyección no es válido.")
    importe = int(candidato.get("importe_centavos") or 0)
    if importe <= 0:
        raise ValueError("El importe proyectado debe ser positivo.")
    try:
        fecha = date.fromisoformat(str(candidato.get("fecha_prevista") or ""))
    except ValueError:
        raise ValueError("La fecha prevista no es válida.")
    movimiento = Movimiento(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
        cuenta_tesoreria_id=cuenta.id, tipo=candidato["tipo"],
        concepto=candidato["concepto"], origen=candidato["origen"],
        referencia=f"{candidato['origen']}:{candidato['origen_id']}",
        importe_centavos=importe, fecha_prevista=fecha,
        clave_idempotencia=candidato["clave_idempotencia"], estado="proyectado",
        confirmado=False, afecta_saldo=False,
        observacion="Confirmada como proyección interna; no implica movimiento de fondos.",
        creado_por_usuario_id=usuario_id,
    )
    db_session.add(movimiento)
    db_session.commit()
    return movimiento
