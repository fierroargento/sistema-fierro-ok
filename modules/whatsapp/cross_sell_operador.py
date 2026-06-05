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


def propuesta_cross_sell_ya_enviada(pedido, evento_operativo_model):
    """
    Devuelve True si ya existe un evento OK de propuesta cross-sell enviada
    para este pedido.

    APB:
    - Evita duplicar mensajes por error.
    - No agrega columnas nuevas.
    - Usa auditoría existente: EventoOperativo.
    """
    pedido_id = getattr(pedido, "id", None)

    if not pedido_id or evento_operativo_model is None:
        return False

    try:
        evento = (
            evento_operativo_model.query
            .filter_by(
                pedido_id=pedido_id,
                tipo_evento="cross_sell_propuesta_operador_enviada",
                resultado="ok",
            )
            .first()
        )

        return evento is not None

    except Exception as e:
        print(f"[WA CROSS-SELL] No se pudo verificar propuesta previa pedido #{pedido_id}: {e}")
        return False



def _url_publica(imagen_relativa, host_url):
    imagen_relativa = (imagen_relativa or "").strip()
    if not imagen_relativa:
        return ""

    if imagen_relativa.startswith("http://") or imagen_relativa.startswith("https://"):
        return imagen_relativa

    return str(host_url or "").rstrip("/") + imagen_relativa

def _armar_texto_propuesta_cross_sell(productos_cross):
    """
    Arma el texto comercial de la propuesta asistida.

    APB:
    - No cierra venta.
    - No informa precio automáticamente.
    - Invita al cliente a pedir precio para que el operador continúe.
    """

    productos_cross = productos_cross or []
    skus = {
        str(p.get("sku") or "").strip().upper()
        for p in productos_cross
    }

    nombres_por_sku = {
        str(p.get("sku") or "").strip().upper(): str(p.get("nombre") or "").strip()
        for p in productos_cross
    }

    # Parrilla plegable PP6040H: kit desarmable + funda.
    if "KPADES" in skus and "BPPC01" in skus:
        nombre_kit = nombres_por_sku.get("KPADES") or "Kit pala y atizador desarmable"
        nombre_funda = nombres_por_sku.get("BPPC01") or "Funda para parrilla plegable"

        return (
            "Antes de cerrar el pedido, te muestro dos accesorios que muchos clientes suman "
            "con la parrilla plegable:\n\n"
            f"- {nombre_kit}\n"
            f"- {nombre_funda}\n\n"
            "El kit es práctico para usar con la parrilla y la funda ayuda a guardarla y transportarla "
            "más cómoda.\n\n"
            "Si querés, te pasamos precio para agregarlos al pedido."
        )

    # Parrillas soldadas/flotantes: kit tradicional + braseros.
    if "KITPACH" in skus and ("B4030H" in skus or "B5030H" in skus):
        nombre_kit = nombres_por_sku.get("KITPACH") or "Kit pala y atizador"
        nombre_brasero_1 = nombres_por_sku.get("B4030H") or "Brasero 30x40"
        nombre_brasero_2 = nombres_por_sku.get("B5030H") or "Brasero 30x53"

        return (
            "Antes de cerrar el pedido, te muestro algunos accesorios que suelen sumar "
            "con esta parrilla:\n\n"
            f"- {nombre_kit}\n"
            f"- {nombre_brasero_1}\n"
            f"- {nombre_brasero_2}\n\n"
            "El kit completa el uso de la parrilla y los braseros son una buena opción para preparar "
            "y mantener las brasas más ordenadas.\n\n"
            "Si querés, te pasamos precio para agregarlos al pedido."
        )

    # Fallback genérico para futuros productos.
    lineas_productos = "\n".join(
        f"- {p.get('nombre') or p.get('sku')}"
        for p in productos_cross
    )

    return (
        "Antes de cerrar el pedido, te muestro algunos accesorios que suelen sumar:\n\n"
        f"{lineas_productos}\n\n"
        "Si querés, te pasamos precio para agregarlos al pedido."
    )

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

    texto_sugerido = _armar_texto_propuesta_cross_sell(productos_cross)

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
    permitir_reenvio=False,
    propuesta_ya_enviada_fn=None,
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

    if callable(propuesta_ya_enviada_fn):
        try:
            ya_enviada = propuesta_ya_enviada_fn(pedido)
        except Exception as e:
            print(f"[WA CROSS-SELL] Error verificando propuesta previa: {e}")
            ya_enviada = False

        if ya_enviada and not permitir_reenvio:
            return (
                False,
                "La propuesta de cross-sell ya fue enviada para este pedido. "
                "Si necesitás reenviarla, usá la opción de reenvío confirmado."
            )

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

    texto_sugerido = _armar_texto_propuesta_cross_sell(productos_cross)

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