"""Helpers puros de Tienda Nube.

Refactor liviano 2:
- Este modulo concentra reglas puras, sin Flask, sin DB y sin efectos secundarios.
- No reemplaza todavia el runtime de app.py: queda preparado para migrar por bloques.
- Objetivo APB: bajar riesgo antes de tocar flujos validados de ML/TN.
"""

ESTADOS_TN_ENVIADO = {
    "fulfilled", "delivered", "shipped", "completed",
    "enviada", "enviado", "despachado", "despachada", "entregado", "entregada",
}

ESTADOS_TN_PAGO_OK = {"paid", "approved", "authorized", "received", "recibido"}
ESTADOS_TN_CANCELADO = {"cancelled", "canceled", "voided"}

CLAVES_TN_TRACKING_NUMERO = {
    "tracking_number", "tracking_code", "tracking", "tracking_id",
    "shipping_tracking_number", "shipping_tracking_code", "shipping_tracking",
    "shipment_tracking_number", "shipment_tracking_code",
    "tracking_codes", "tracking_numbers", "code_tracking",
    "codigo_seguimiento", "numero_seguimiento", "nro_seguimiento",
}

CLAVES_TN_TRACKING_URL = {
    "tracking_url", "tracking_link", "tracking_page", "tracking_url_public",
    "shipping_tracking_url", "shipment_tracking_url",
}


def texto_multilenguaje(valor):
    if isinstance(valor, dict):
        return valor.get("es") or valor.get("pt") or valor.get("en") or next(iter(valor.values()), "")
    return valor or ""


def pago_confirmado(order):
    payment_status = str(order.get("payment_status") or order.get("financial_status") or "").lower().strip()
    return payment_status in ESTADOS_TN_PAGO_OK


def pedido_cancelado(order):
    status = str(order.get("status") or "").lower().strip()
    return bool(status in ESTADOS_TN_CANCELADO or order.get("cancelled_at"))


def pedido_ya_enviado(order):
    """Devuelve True solo si TN ya considera el pedido enviado/cumplido.

    APB TN:
    - Por empaquetar => entra
    - Por enviar => entra
    - Enviada/despachada/entregada => no entra como pedido nuevo
    """
    fulfillment_status = str(order.get("fulfillment_status") or order.get("shipping_status") or "").lower().strip()
    shipping_data = order.get("shipping") if isinstance(order.get("shipping"), dict) else {}
    shipping_status = str(
        shipping_data.get("status")
        or shipping_data.get("fulfillment_status")
        or shipping_data.get("shipment_status")
        or ""
    ).lower().strip()
    if fulfillment_status in ESTADOS_TN_ENVIADO or shipping_status in ESTADOS_TN_ENVIADO:
        return True
    texto = " ".join([fulfillment_status, shipping_status])
    return any(indicador in texto for indicador in ESTADOS_TN_ENVIADO)


def pedido_apto_para_fierro(order):
    if not order:
        return False, "pedido vacio"
    if pedido_cancelado(order):
        return False, "pedido cancelado"
    if not pago_confirmado(order):
        estado_pago = str(order.get("payment_status") or order.get("financial_status") or "sin estado")
        return False, f"pago no confirmado: {estado_pago}"
    if pedido_ya_enviado(order):
        return False, "pedido ya enviado/entregado"
    return True, "ok"


def tracking_sospechoso(valor):
    valor = str(valor or "").strip()
    if not valor:
        return True
    if valor.isdigit() and len(valor) < 8:
        return True
    return False


def extraer_tracking(order):
    """Extrae tracking TN de forma defensiva.

    Evita confundir campos genericos como `number` con el seguimiento real.
    Caso real ya resuelto: valores cortos/numericos tipo 319 no se aceptan
    como tracking.
    """
    candidatos = []

    order_id = str(order.get("id") or "").strip()
    order_number = str(order.get("number") or order.get("order_number") or "").strip()

    def valor_valido(numero):
        numero = str(numero or "").strip()
        if not numero:
            return ""
        if numero in {order_id, order_number}:
            return ""
        if numero.isdigit() and len(numero) < 8:
            return ""
        return numero

    def agregar(numero="", url=""):
        numero = valor_valido(numero)
        url = str(url or "").strip()
        if numero or url:
            candidatos.append((numero, url))

    def recorrer(obj):
        if isinstance(obj, dict):
            tracking_info = obj.get("tracking_info")
            if isinstance(tracking_info, dict):
                agregar(tracking_info.get("code"), tracking_info.get("url"))

            tracking_history = obj.get("tracking_info_history") or []
            if isinstance(tracking_history, list):
                for hist in tracking_history:
                    if isinstance(hist, dict):
                        to_info = hist.get("to_tracking_info")
                        from_info = hist.get("from_tracking_info")
                        if isinstance(to_info, dict):
                            agregar(to_info.get("code"), to_info.get("url"))
                        if isinstance(from_info, dict):
                            agregar(from_info.get("code"), from_info.get("url"))

            numero = ""
            url = ""
            for k, v in obj.items():
                kl = str(k).lower().strip()
                if kl in CLAVES_TN_TRACKING_NUMERO:
                    if isinstance(v, list):
                        for item in v:
                            agregar(item, "")
                    elif isinstance(v, dict):
                        recorrer(v)
                    else:
                        numero = numero or str(v or "").strip()
                elif kl in CLAVES_TN_TRACKING_URL:
                    url = url or str(v or "").strip()
            agregar(numero, url)
            for v in obj.values():
                if isinstance(v, (dict, list)):
                    recorrer(v)
        elif isinstance(obj, list):
            for item in obj:
                recorrer(item)

    recorrer(order)

    con_numero = [(n, u) for n, u in candidatos if n]
    if con_numero:
        con_numero.sort(key=lambda par: (len(par[0]), any(c.isalpha() for c in par[0])), reverse=True)
        return con_numero[0]

    for numero, url in candidatos:
        if url:
            return numero, url
    return "", ""


# Alias con nombres equivalentes a app.py para futura migracion controlada.
tn_texto_multilenguaje = texto_multilenguaje
tn_pago_confirmado = pago_confirmado
tn_pedido_cancelado = pedido_cancelado
tn_pedido_ya_enviado = pedido_ya_enviado
tn_tracking_sospechoso = tracking_sospechoso
tn_extraer_tracking = extraer_tracking
