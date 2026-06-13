"""
modules.bot_ml.mensajes
-----------------------
Parsers y helpers puros para mensajes de Mercado Libre.

APB / SaaS:
- No consulta API.
- No escribe DB.
- No depende de Flask ni app.py.
- Solo interpreta estructuras de mensajes ML ya recibidas.
"""

import re


def ml_extraer_ids_mensaje_ml(obj):
    """
    Extrae IDs relacionados a mensajes ML de forma robusta.
    Contempla pack_id, order_id, recursos /packs/{id}/orders/{id}
    y el formato frecuente de ML message_resources: [{id, name: packs/orders}].
    """
    ids = set()

    def agregar(valor):
        valor = str(valor or "").strip()
        if not valor:
            return
        if re.fullmatch(r"\d{8,}", valor):
            ids.add(valor)

    def recorrer(valor, clave=""):
        clave_l = str(clave or "").lower()

        if isinstance(valor, dict):
            nombre_recurso = str(
                valor.get("name")
                or valor.get("resource")
                or valor.get("resource_type")
                or valor.get("type")
                or ""
            ).lower()
            id_recurso = (
                valor.get("id")
                or valor.get("resource_id")
                or valor.get("pack_id")
                or valor.get("order_id")
            )
            if any(x in nombre_recurso for x in ["pack", "order"]):
                agregar(id_recurso)

            for k, v in valor.items():
                recorrer(v, k)
            return

        if isinstance(valor, list):
            for v in valor:
                recorrer(v, clave_l)
            return

        texto = str(valor or "").strip()
        if not texto:
            return

        if any(x in clave_l for x in ["pack", "order"]):
            agregar(texto)

        for patron in [
            r"/packs/([^/?#]+)",
            r"/orders/([^/?#]+)",
            r"pack_id[=:]([^&/?#]+)",
            r"order_id[=:]([^&/?#]+)",
        ]:
            for match in re.finditer(patron, texto):
                agregar(match.group(1))

    recorrer(obj)
    return ids


def ml_extraer_lista_mensajes_ml(data):
    """Extrae mensajes desde varias estructuras posibles de la API de ML."""
    mensajes = []

    def caminar(valor):
        if isinstance(valor, dict):
            for clave in ("messages", "results", "items"):
                posible = valor.get(clave)
                if isinstance(posible, list):
                    for item in posible:
                        if isinstance(item, dict) and (
                            "from" in item
                            or "sender" in item
                            or "text" in item
                            or "message" in item
                            or "status" in item
                        ):
                            mensajes.append(item)

            for v in valor.values():
                caminar(v)

        elif isinstance(valor, list):
            for v in valor:
                caminar(v)

    caminar(data)

    unicos = []
    vistos = set()

    for m in mensajes:
        mid = str(m.get("id") or m.get("message_id") or "").strip()
        clave = mid or str(m)[:300]

        if clave in vistos:
            continue

        vistos.add(clave)
        unicos.append(m)

    return unicos


def ml_mensaje_es_del_comprador(m, seller_id=""):
    """Determina si un mensaje vino del comprador."""
    if not isinstance(m, dict):
        return False

    from_data = m.get("from") or m.get("sender") or m.get("user") or {}
    if not isinstance(from_data, dict):
        from_data = {}

    user_type = str(
        from_data.get("user_type")
        or from_data.get("role")
        or from_data.get("type")
        or m.get("from_user_type")
        or ""
    ).lower().strip()

    if user_type in {"buyer", "comprador"}:
        return True

    if user_type in {"seller", "vendedor", "operator", "admin"}:
        return False

    sender_id = str(
        from_data.get("id")
        or from_data.get("user_id")
        or m.get("from_id")
        or ""
    ).strip()

    return bool(sender_id and seller_id and sender_id != str(seller_id))


def ml_mensaje_es_del_vendedor(m, seller_id=""):
    """Determina si un mensaje vino del vendedor/cuenta Fierro."""
    if not isinstance(m, dict):
        return False

    seller_id = str(seller_id or "").strip()
    posibles_from = [m.get("from"), m.get("sender"), m.get("author")]

    for f in posibles_from:
        if isinstance(f, dict):
            user_type = str(f.get("user_type") or f.get("type") or f.get("role") or "").lower()

            if user_type in {"seller", "vendor"}:
                return True

            fid = str(f.get("id") or f.get("user_id") or "").strip()
            if seller_id and fid and fid == seller_id:
                return True

    for key in ["from_user_id", "sender_id", "user_id"]:
        val = str(m.get(key) or "").strip()
        if seller_id and val and val == seller_id:
            return True

    return False


def ml_mensaje_esta_pendiente(m):
    """Detecta si el mensaje requiere atencion sin marcarlo como leido."""
    if not isinstance(m, dict):
        return False

    status = str(
        m.get("status")
        or m.get("message_status")
        or m.get("read_status")
        or ""
    ).lower().strip()

    if status in {"unread", "new", "pending", "not_read", "unanswered"}:
        return True

    if status in {"read", "answered", "closed"}:
        return False

    for clave in ("read", "is_read", "answered", "is_answered"):
        if clave in m:
            valor = m.get(clave)

            if clave in {"read", "is_read"} and valor is False:
                return True

            if clave in {"answered", "is_answered"} and valor is False:
                return True

    date_data = m.get("message_date") or m.get("date") or {}
    if isinstance(date_data, dict) and "read" in date_data and not date_data.get("read"):
        return True

    return False


def ml_fecha_mensaje_valor(m):
    """Devuelve una fecha comparable del mensaje ML si existe."""
    if not isinstance(m, dict):
        return ""

    candidatos = [
        m.get("date_created"),
        m.get("created_at"),
        m.get("date"),
        m.get("message_date"),
    ]

    for c in candidatos:
        if isinstance(c, dict):
            for k in ("created", "date", "sent", "received", "read"):
                if c.get(k):
                    return str(c.get(k))
        elif c:
            return str(c)

    return ""


def ml_texto_mensaje_ml(m):
    """Extrae texto visible de un mensaje ML sin marcarlo como leido."""
    if not isinstance(m, dict):
        return ""

    candidatos = [
        m.get("text"),
        m.get("message"),
        m.get("body"),
        m.get("plain"),
        m.get("content"),
    ]

    for valor in candidatos:
        if isinstance(valor, str) and valor.strip():
            return valor.strip()

        if isinstance(valor, dict):
            for key in ["plain", "text", "message", "body", "content"]:
                sub = valor.get(key)
                if isinstance(sub, str) and sub.strip():
                    return sub.strip()

    attachments = m.get("attachments") or []
    if attachments:
        return "[El comprador envio un adjunto o imagen]"

    return ""


def ml_ultimo_mensaje_comprador(mensajes, seller_id=""):
    """Devuelve el ultimo mensaje de comprador con texto util."""
    if not mensajes:
        return None

    candidatos = [
        m for m in mensajes
        if ml_mensaje_es_del_comprador(m, seller_id=seller_id)
        and ml_texto_mensaje_ml(m)
    ]

    if not candidatos:
        return None

    try:
        candidatos.sort(key=ml_fecha_mensaje_valor)
    except Exception:
        pass

    return candidatos[-1]


def ml_bloque_mensajes_comprador_pendientes(mensajes, seller_id=""):
    """
    APB Recolector ML:
    Devuelve el bloque de mensajes del comprador posteriores
    al ultimo mensaje del vendedor/bot.
    """
    if not mensajes:
        return ""

    ordenados = list(mensajes or [])

    try:
        ordenados.sort(key=ml_fecha_mensaje_valor)
    except Exception:
        pass

    ultimo_idx_vendedor = -1

    for idx, m in enumerate(ordenados):
        if ml_mensaje_es_del_vendedor(m, seller_id=seller_id):
            ultimo_idx_vendedor = idx

    textos = []

    for m in ordenados[ultimo_idx_vendedor + 1:]:
        if not ml_mensaje_es_del_comprador(m, seller_id=seller_id):
            continue

        texto = ml_texto_mensaje_ml(m)
        if texto:
            textos.append(texto.strip())

    bloque = "\n\n".join(textos).strip()

    if len(bloque) > 3000:
        bloque = bloque[-3000:]

    return bloque