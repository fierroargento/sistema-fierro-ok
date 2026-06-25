"""
services/wa_general.py

Bandeja WhatsApp General.

Regla:
- WA General muestra conversaciones por teléfono que NO tienen pedido activo.
- Incluye contactos nuevos.
- Incluye clientes cuyo último pedido ya está cerrado/finalizado.
- No mezcla conversaciones operativas de pedidos activos.
"""

from dataclasses import dataclass
from datetime import datetime


ESTADOS_PEDIDO_ACTIVO = {
    "Cargando Pedido",
    "Etiqueta Lista",
    "Etiqueta Impresa",
    "Embalado",
    "Despachado",
    "Verificar llegada a destino",
    "Listo para retirar",
    "Con demora de entrega",
    "Con reclamo en transporte",
    "Reclamar a Mercado Libre",
}


@dataclass
class WAConversacionGeneral:
    telefono: str
    nombre: str
    ultimo_mensaje: str
    ultima_actividad: datetime | None
    no_leidos: int
    pedido_contexto_id: int | None
    pedido_contexto_estado: str
    pedidos_historicos: list


def pedido_esta_activo_para_wa_general(pedido):
    if not pedido:
        return False

    estado = str(getattr(pedido, "estado", "") or "").strip()
    return estado in ESTADOS_PEDIDO_ACTIVO


def normalizar_telefono_simple(valor):
    return "".join(ch for ch in str(valor or "") if ch.isdigit())


def obtener_pedidos_por_telefono(telefono, Pedido):
    tel = normalizar_telefono_simple(telefono)
    if not tel:
        return []

    pedidos = (
        Pedido.query
        .filter(Pedido.telefono.isnot(None))
        .order_by(Pedido.id.desc())
        .limit(300)
        .all()
    )

    encontrados = []
    for pedido in pedidos:
        tel_pedido = normalizar_telefono_simple(getattr(pedido, "telefono", ""))
        if tel_pedido and tel_pedido == tel:
            encontrados.append(pedido)

    return encontrados


def armar_conversaciones_wa_general(WhatsAppMensaje, Pedido, limite=50):
    """
    Devuelve conversaciones generales agrupadas por teléfono.

    Importante:
    - Si el teléfono tiene algún pedido activo, NO aparece en WA General.
    - Si no tiene pedido activo, aparece con historial de pedidos cerrados si existen.
    """

    mensajes = (
        WhatsAppMensaje.query
        .filter(WhatsAppMensaje.telefono.isnot(None))
        .order_by(WhatsAppMensaje.fecha.desc())
        .limit(1000)
        .all()
    )

    por_telefono = {}

    for mensaje in mensajes:
        telefono = normalizar_telefono_simple(getattr(mensaje, "telefono", ""))
        if not telefono:
            continue

        if telefono not in por_telefono:
            por_telefono[telefono] = {
                "telefono": telefono,
                "ultimo_mensaje": getattr(mensaje, "texto", "") or "",
                "ultima_actividad": getattr(mensaje, "fecha", None),
                "no_leidos": 0,
            }

        direccion = str(getattr(mensaje, "direccion", "") or "").strip().lower()
        estado = str(getattr(mensaje, "estado", "") or "").strip().lower()

        if direccion == "in" and estado in {"recibido", "pendiente", ""}:
            por_telefono[telefono]["no_leidos"] += 1

    conversaciones = []

    for telefono, data in por_telefono.items():
        pedidos = obtener_pedidos_por_telefono(telefono, Pedido)

        if any(pedido_esta_activo_para_wa_general(p) for p in pedidos):
            continue

        pedido_contexto = pedidos[0] if pedidos else None

        nombre = ""
        if pedido_contexto:
            nombre = str(getattr(pedido_contexto, "cliente", "") or "").strip()

        conversaciones.append(WAConversacionGeneral(
            telefono=telefono,
            nombre=nombre or telefono,
            ultimo_mensaje=(data["ultimo_mensaje"] or "")[:300],
            ultima_actividad=data["ultima_actividad"],
            no_leidos=data["no_leidos"],
            pedido_contexto_id=getattr(pedido_contexto, "id", None) if pedido_contexto else None,
            pedido_contexto_estado=str(getattr(pedido_contexto, "estado", "") or "") if pedido_contexto else "",
            pedidos_historicos=pedidos[:10],
        ))

    conversaciones.sort(
        key=lambda c: c.ultima_actividad or datetime.min,
        reverse=True,
    )

    return conversaciones[:limite]
