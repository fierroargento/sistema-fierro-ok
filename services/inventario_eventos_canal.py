"""Contratos multicanal preparados; no están conectados a webhooks ni stock."""

import hashlib
import json

from services.inventario_pedidos import agrupar_items_pedido


TIPOS_EVENTO = frozenset({
    "reservar", "liberar", "consumir", "revisar_devolucion",
})


def normalizar_cantidades(cantidades):
    normalizadas = {}
    if isinstance(cantidades, dict):
        pares = cantidades.items()
    else:
        pares = agrupar_items_pedido(cantidades).items()
    for sku, cantidad in pares:
        sku_normalizado = str(sku or "").strip().upper()
        try:
            cantidad_normalizada = int(cantidad or 0)
        except (TypeError, ValueError) as error:
            raise ValueError("Las cantidades del evento deben ser enteras.") from error
        if sku_normalizado and cantidad_normalizada > 0:
            normalizadas[sku_normalizado] = (
                normalizadas.get(sku_normalizado, 0) + cantidad_normalizada
            )
    if not normalizadas:
        raise ValueError("El evento no contiene cantidades inventariables.")
    return normalizadas


def crear_contrato_evento(
    *, canal, referencia, tipo_evento, cantidades, estado_origen="", parcial=False,
):
    tipo = str(tipo_evento or "").strip().lower()
    if tipo not in TIPOS_EVENTO:
        raise ValueError("El tipo de evento multicanal no es válido.")
    canal_normalizado = str(canal or "").strip().lower().replace(" ", "_")
    referencia_normalizada = str(referencia or "").strip()
    if not canal_normalizado or not referencia_normalizada:
        raise ValueError("El evento necesita canal y referencia externa.")
    cantidades_normalizadas = normalizar_cantidades(cantidades)
    return {
        "version": 1,
        "canal": canal_normalizado,
        "referencia": referencia_normalizada,
        "tipo_evento": tipo,
        "cantidades": cantidades_normalizadas,
        "parcial": bool(parcial),
        "estado_origen": str(estado_origen or "").strip().lower(),
        "requiere_revision": tipo == "revisar_devolucion",
        "modo": "desconectado",
    }


def contrato_desde_pedido(pedido, *, evento_externo=None, cantidades=None):
    """Traduce estados conocidos sin ejecutar el contrato resultante."""
    canal = str(getattr(pedido, "canal", "") or "").strip()
    estado = str(
        evento_externo
        or getattr(pedido, "estado", "")
        or ""
    ).strip().lower()
    if any(valor in estado for valor in ("cancel", "anulad")):
        tipo = "liberar"
    elif any(valor in estado for valor in ("devol", "return", "refund")):
        tipo = "revisar_devolucion"
    elif any(valor in estado for valor in ("despach", "shipped", "fulfilled")):
        tipo = "consumir"
    else:
        tipo = "reservar"
    referencia = (
        getattr(pedido, "id_venta", None)
        or getattr(pedido, "ml_pack_id", None)
        or getattr(pedido, "tn_order_id", None)
        or getattr(pedido, "id", None)
    )
    return crear_contrato_evento(
        canal=canal,
        referencia=referencia,
        tipo_evento=tipo,
        cantidades=cantidades if cantidades is not None else getattr(pedido, "items", ()),
        estado_origen=estado,
        parcial=cantidades is not None,
    )


def contrato_puede_ejecutarse(contrato, configuracion):
    """Permanece falso mientras el adaptador esté desconectado de producción."""
    return bool(
        contrato
        and contrato.get("modo") == "productivo"
        and str(getattr(configuracion, "estado", "")) == "activo"
    )


def resolver_identidad_cuenta(pedido):
    """Exige la cuenta exacta que originó el pedido; nunca infiere por canal."""
    canal = str(getattr(pedido, "canal", "") or "").strip().lower()
    if "mercado" in canal:
        cuenta_id = int(getattr(pedido, "ml_cuenta_id", 0) or 0)
        cuenta_tipo = "mercado_libre"
    elif "tienda" in canal:
        cuenta_id = int(getattr(pedido, "tn_cuenta_id", 0) or 0)
        cuenta_tipo = "tienda_nube"
    else:
        raise ValueError("El pedido no conserva un canal empresarial compatible.")
    if not cuenta_id:
        raise ValueError("El pedido no conserva la cuenta empresarial de origen.")
    return cuenta_tipo, cuenta_id


def preparar_sobre_evento(
    pedido,
    *,
    organizacion_id,
    evento_externo_id,
    evento_externo=None,
    cantidades=None,
):
    """Crea un sobre auditable y determinista sin persistir ni ejecutar stock."""
    identificador_evento = str(evento_externo_id or "").strip()
    if not identificador_evento:
        raise ValueError("El evento necesita un identificador externo idempotente.")
    cuenta_tipo, cuenta_id = resolver_identidad_cuenta(pedido)
    contrato = contrato_desde_pedido(
        pedido,
        evento_externo=evento_externo,
        cantidades=cantidades,
    )
    contenido = {
        "organizacion_id": int(organizacion_id),
        "pedido_id": int(getattr(pedido, "id", 0) or 0),
        "cuenta_tipo": cuenta_tipo,
        "cuenta_id": cuenta_id,
        "evento_externo_id": identificador_evento,
        "contrato": contrato,
    }
    serializado = json.dumps(
        contenido, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    payload_hash = hashlib.sha256(serializado.encode("utf-8")).hexdigest()
    clave = (
        f"org:{int(organizacion_id)}:{cuenta_tipo}:{cuenta_id}:"
        f"evento:{identificador_evento}"
    )
    return {
        **contenido,
        "clave_idempotencia": clave,
        "payload_hash": payload_hash,
        "estado": "preparado_sin_conexion",
        "contrato_json": serializado,
    }


def registrar_sobre_desconectado(sobre, *, EventoCanal, db_session):
    """Registra una sola vez el contrato; no invoca reservas ni movimientos."""
    organizacion_id = int(sobre["organizacion_id"])
    clave = str(sobre["clave_idempotencia"])
    existente = EventoCanal.query.filter_by(
        organizacion_id=organizacion_id,
        clave_idempotencia=clave,
    ).first()
    if existente is not None:
        if str(existente.payload_hash) != str(sobre["payload_hash"]):
            raise ValueError(
                "La clave externa ya existe con un contenido diferente."
            )
        return existente, False
    contrato = sobre["contrato"]
    evento = EventoCanal(
        organizacion_id=organizacion_id,
        pedido_id=sobre["pedido_id"],
        canal=contrato["canal"],
        cuenta_tipo=sobre["cuenta_tipo"],
        cuenta_id=sobre["cuenta_id"],
        referencia_externa=contrato["referencia"],
        evento_externo_id=sobre["evento_externo_id"],
        tipo_evento=contrato["tipo_evento"],
        clave_idempotencia=clave,
        estado="preparado_sin_conexion",
        parcial=bool(contrato["parcial"]),
        requiere_revision=bool(contrato["requiere_revision"]),
        contrato_json=sobre["contrato_json"],
        payload_hash=sobre["payload_hash"],
    )
    db_session.add(evento)
    db_session.commit()
    return evento, True
