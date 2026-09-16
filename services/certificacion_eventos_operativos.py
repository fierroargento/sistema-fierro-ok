"""Certificación tenant de eventos operativos, sin modificar registros."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json


def obtener_eventos_tenant(organizacion_id, *, Pedido, EventoOperativo, limite=1000):
    pedidos = Pedido.query.filter_by(organizacion_id=int(organizacion_id)).all()
    ids = [p.id for p in pedidos]
    if not ids:
        return [], {}
    eventos = (EventoOperativo.query.filter(EventoOperativo.pedido_id.in_(ids))
               .order_by(EventoOperativo.id.desc()).limit(max(1, min(int(limite), 1000))).all())
    return eventos, {p.id: p for p in pedidos}


def certificar_eventos(organizacion_id, eventos, pedidos):
    organizacion_id = int(organizacion_id); observaciones=[]; filas=[]; tipos=Counter(); vistos=set()
    for evento in eventos:
        errores=[]; pedido=pedidos.get(evento.pedido_id); tipos[str(evento.tipo_evento)] += 1
        if pedido is None: errores.append("pedido_huerfano_o_ajeno")
        elif getattr(pedido, "organizacion_id", None) != organizacion_id: errores.append("pedido_tenant_cruzado")
        if evento.id in vistos: errores.append("evento_duplicado")
        vistos.add(evento.id)
        if not str(evento.tipo_evento or "").strip(): errores.append("tipo_evento_vacio")
        observaciones.extend({"evento_id":evento.id,"codigo":codigo} for codigo in errores)
        filas.append({"evento_id":evento.id,"pedido_id":evento.pedido_id,"tipo_evento":evento.tipo_evento,
                      "procesado":bool(evento.procesado),"resultado":"observado" if errores else "valido"})
    cuerpo={"tipo":"certificacion_eventos_operativos_tenant","version":1,"organizacion_id":organizacion_id,
            "total":len(filas),"tipos":dict(sorted(tipos.items())),"observaciones":observaciones,
            "eventos":filas,"aprobado":not observaciones,"solo_lectura":True,
            "eventos_modificados":0,"eventos_sin_pedido_excluidos":True}
    canonico=json.dumps(cuerpo,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    cuerpo["firma_sha256"]=sha256(canonico.encode("utf-8")).hexdigest()
    cuerpo["generado_utc"]=datetime.now(timezone.utc).isoformat()
    return cuerpo


def exportar_certificacion(certificacion):
    return BytesIO(json.dumps(certificacion,ensure_ascii=False,sort_keys=True,indent=2).encode("utf-8"))
