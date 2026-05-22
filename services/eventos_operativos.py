import json
from datetime import datetime, UTC


def registrar_evento_operativo_service(
    EventoOperativo,
    db,
    pedido=None,
    tipo_evento="",
    origen="sistema",
    canal="sistema",
    owner="sistema",
    estado_conversacional="",
    flujo_base="",
    payload=None,
    resultado="",
    detalle="",
    usuario="",
    procesado=False,
):
    """
    Registra un evento operativo APB sin romper el flujo si falla.
    """

    if not tipo_evento:
        return None

    try:
        evento = EventoOperativo(
            pedido_id=getattr(pedido, "id", None),
            tipo_evento=str(tipo_evento)[:120],
            origen=str(origen or "")[:50],
            canal=str(canal or "")[:30],
            owner=str(owner or "")[:30],
            estado_conversacional=str(estado_conversacional or "")[:80],
            flujo_base=str(flujo_base or "")[:80],
            payload_json=json.dumps(payload or {}, ensure_ascii=False),
            resultado=str(resultado or "")[:80],
            detalle=str(detalle or "")[:2000],
            usuario=str(usuario or "")[:100],
            procesado=bool(procesado),
            fecha=datetime.now(UTC),
        )

        db.session.add(evento)
        db.session.commit()

        return evento

    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass

        print("[EVENTO-OPERATIVO] No se pudo registrar evento:", e)

        return None