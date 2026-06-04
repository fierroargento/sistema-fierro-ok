from datetime import datetime

from domain.estados import Estado
from modules.whatsapp.config import CROSS_SELL_MANUAL_ENABLED
from modules.whatsapp.cross_sell import obtener_productos_a_ofrecer, obtener_producto
from modules.whatsapp.sender import wa_enviar_texto, wa_enviar_imagen


ESTADOS_SIN_CROSS_SELL = {
    Estado.DESPACHADO,
    Estado.VERIFICAR_DESTINO,
    Estado.LISTO_RETIRAR,
    Estado.DEMORA,
    Estado.RECLAMO,
    Estado.NO_ENTREGADO,
    Estado.ENTREGADO,
    Estado.FINALIZADO,
    Estado.CANCELADO,
    Estado.RECLAMAR_ML,
}


def puede_usar_cross_sell_operador(pedido):
    """
    APB:
    Cross-sell manual solo antes de Despachado.
    Desde Despachado inclusive en adelante, no se ofrece ni se ejecuta.
    """
    return bool(
        CROSS_SELL_MANUAL_ENABLED
        and pedido
        and getattr(pedido, "estado", None) not in ESTADOS_SIN_CROSS_SELL
    )


def _url_publica(imagen_relativa, host_url):
    imagen_relativa = (imagen_relativa or "").strip()
    if not imagen_relativa:
        return ""

    if imagen_relativa.startswith("http://") or imagen_relativa.startswith("https://"):
        return imagen_relativa

    return str(host_url or "").rstrip("/") + imagen_relativa


def preparar_propuesta_cross_sell_operador(pedido):
    """
    Prepara la propuesta que se muestra al operador.
    No envía nada.
    """
    if not puede_usar_cross_sell_operador(pedido):
        return None

    productos_cross = []
    nombres_cross = []

    for sku_cross in obtener_productos_a_ofrecer(pedido):
        producto_cross = obtener_producto(sku_cross) or {}
        nombre_cross = producto_cross.get("nombre", sku_cross)
        imagen_url = (producto_cross.get("imagen_url") or "").strip()

        productos_cross.append({
            "sku": sku_cross,
            "nombre": nombre_cross,
            "descripcion": producto_cross.get("descripcion", ""),
            "imagen_url": imagen_url,
            "tiene_imagen": bool(imagen_url),
        })

        nombres_cross.append(nombre_cross)

    if not productos_cross:
        return None

    lineas_productos = "\n".join([f"- {nombre}" for nombre in nombres_cross])

    texto_sugerido = (
        "Antes de cerrar el pedido, te muestro algunos accesorios que suelen sumar:\n\n"
        f"{lineas_productos}\n\n"
        "Si querés, te pasamos precio para agregarlos al pedido."
    )

    return {
        "texto": texto_sugerido,
        "productos": productos_cross,
    }


def enviar_propuesta_cross_sell_operador(
    pedido,
    *,
    db,
    usuario,
    host_url,
    normalizar_telefono_fn,
    actualizar_estado_conversacional_fn,
    registrar_evento_operativo_fn,
):
    """
    Envía texto + imágenes de propuesta cross-sell.
    Deja la conversación en operador_manual y pausa el bot.
    """

    if not CROSS_SELL_MANUAL_ENABLED:
        return False, "Cross-sell manual deshabilitado por configuración."

    if not puede_usar_cross_sell_operador(pedido):
        return False, "No se puede enviar propuesta de cross-sell porque el pedido ya fue despachado o está en una etapa posterior."

    tel = normalizar_telefono_fn(getattr(pedido, "telefono", ""))

    if not tel:
        return False, "El pedido no tiene teléfono válido para WhatsApp."

    productos_cross = []
    nombres_cross = []

    for sku_cross in obtener_productos_a_ofrecer(pedido):
        producto_cross = obtener_producto(sku_cross) or {}
        nombre_cross = producto_cross.get("nombre", sku_cross)
        imagen_relativa = (producto_cross.get("imagen_url") or "").strip()

        productos_cross.append({
            "sku": sku_cross,
            "nombre": nombre_cross,
            "descripcion": producto_cross.get("descripcion", ""),
            "imagen_url": _url_publica(imagen_relativa, host_url),
        })

        nombres_cross.append(nombre_cross)

    if not productos_cross:
        return False, "Este pedido no tiene agregados configurados para ofrecer."

    lineas_productos = "\n".join([f"- {nombre}" for nombre in nombres_cross])

    texto_sugerido = (
        "Antes de cerrar el pedido, te muestro algunos accesorios que suelen sumar:\n\n"
        f"{lineas_productos}\n\n"
        "Si querés, te pasamos precio para agregarlos al pedido."
    )

    ok_texto = wa_enviar_texto(
        tel,
        texto_sugerido,
        pedido=pedido,
        autor="operador",
    )

    imagenes_enviadas = []
    imagenes_fallidas = []

    for producto_cross in productos_cross:
        imagen_url = producto_cross.get("imagen_url", "")

        if not imagen_url:
            continue

        ok_img = wa_enviar_imagen(
            tel,
            imagen_url,
            caption=producto_cross.get("nombre", ""),
            pedido=pedido,
            autor="operador",
        )

        if ok_img:
            imagenes_enviadas.append(producto_cross.get("sku"))
        else:
            imagenes_fallidas.append(producto_cross.get("sku"))

    if not ok_texto and not imagenes_enviadas:
        return False, "No se pudo enviar la propuesta por WhatsApp API."

    pedido.wa_estado = "operador_manual"
    pedido.ia_requiere_operador = True
    pedido.wa_ultimo_contacto = datetime.utcnow()

    actualizar_estado_conversacional_fn(
        pedido,
        owner_actual="operador",
        canal_activo="wa",
        estado_conversacional="cross_sell_propuesta_operador",
        takeover_activo=True,
        bot_pausado=True,
        cross_sell_activo=False,
    )

    registrar_evento_operativo_fn(
        pedido=pedido,
        tipo_evento="cross_sell_propuesta_operador_enviada",
        origen="operador",
        canal="wa",
        owner="operador",
        estado_conversacional="cross_sell_propuesta_operador",
        payload={
            "texto": texto_sugerido,
            "productos": productos_cross,
            "imagenes_enviadas": imagenes_enviadas,
            "imagenes_fallidas": imagenes_fallidas,
        },
        resultado="ok",
        detalle="Operador envió propuesta asistida de cross-sell por WhatsApp. El bot queda pausado.",
        usuario=usuario,
        procesado=True,
    )

    db.session.commit()

    if imagenes_fallidas:
        return True, "Propuesta enviada, pero alguna imagen no se pudo enviar por WhatsApp."

    return True, "Propuesta de cross-sell enviada por WhatsApp. El operador sigue a cargo de la conversación."