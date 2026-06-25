"""
services/wa_general.py

Bandeja WhatsApp General.

Regla:
- WA General muestra conversaciones por telefono que NO tienen pedido activo.
- Incluye mensajes generales sin pedido_id.
- Incluye clientes que vuelven a escribir despues de que su pedido fue Entregado/Finalizado.
- No lista automaticamente historicos viejos de postventa o flujos operativos.
- No mezcla conversaciones de pedidos activos.
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

ESTADOS_PEDIDO_POST_ENTREGA = {
    "Entregado",
    "Finalizado",
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


def pedido_esta_post_entrega_para_wa_general(pedido):
    if not pedido:
        return False

    estado = str(getattr(pedido, "estado", "") or "").strip()
    return estado in ESTADOS_PEDIDO_POST_ENTREGA


def normalizar_telefono_simple(valor):
    return "".join(ch for ch in str(valor or "") if ch.isdigit())


def mensaje_tiene_pedido_id(mensaje):
    pedido_id = getattr(mensaje, "pedido_id", None)
    return pedido_id not in {None, "", 0}


def mensaje_es_entrante_cliente(mensaje):
    direccion = str(getattr(mensaje, "direccion", "") or "").strip().lower()
    return direccion == "in"


def obtener_pedido_por_id(Pedido, pedido_id):
    if not pedido_id:
        return None

    return Pedido.query.filter(Pedido.id == pedido_id).first()


def mensaje_es_posterior_a_entrega(mensaje, pedido):
    fecha_mensaje = getattr(mensaje, "fecha", None)
    fecha_entregado = getattr(pedido, "fecha_entregado", None)

    if not fecha_mensaje or not fecha_entregado:
        return False

    return fecha_mensaje >= fecha_entregado


def mensaje_es_general_para_wa_general(mensaje, Pedido):
    """
    Define si un mensaje puede abrir conversacion en WA General.

    Entra si:
    - No tiene pedido_id.
    - O tiene pedido_id, pero es un mensaje entrante posterior a la entrega
      de un pedido Entregado/Finalizado.

    No entra si:
    - Es un mensaje operativo de un pedido activo.
    - Es una postventa automatica vieja.
    - Es un mensaje saliente asociado a un pedido cerrado sin respuesta nueva del cliente.
    """

    if not mensaje_tiene_pedido_id(mensaje):
        return True

    if not mensaje_es_entrante_cliente(mensaje):
        return False

    pedido = obtener_pedido_por_id(Pedido, getattr(mensaje, "pedido_id", None))

    if not pedido_esta_post_entrega_para_wa_general(pedido):
        return False

    return mensaje_es_posterior_a_entrega(mensaje, pedido)


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
    Devuelve conversaciones generales agrupadas por telefono.

    Importante:
    - La lista izquierda no se arma con todo el historial.
    - Incluye mensajes sin pedido_id.
    - Incluye mensajes entrantes posteriores a entrega de pedidos Entregado/Finalizado.
    - Si el telefono tiene algun pedido activo, NO aparece en WA General.
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
        if not mensaje_es_general_para_wa_general(mensaje, Pedido):
            continue

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
