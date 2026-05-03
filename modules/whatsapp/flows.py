"""
modules/whatsapp/flows.py
─────────────────────────
Flujos conversacionales completos del bot.
Cada función maneja un estado del pedido y las respuestas posibles del cliente.
"""

import re
from datetime import datetime, timedelta

from .config import (
    ALIAS_PAGO, TIMER_PRIMER_RECORDATORIO,
    TIMER_SEGUNDO_RECORDATORIO, TIMER_CROSS_SELL_SIGUIENTE,
)
from .sender import wa_enviar_texto
from .cross_sell import (
    obtener_productos_a_ofrecer, wa_ofrecer_producto,
    wa_responder_precio, wa_cerrar_cross_sell, wa_escalar_venta_cerrada,
)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _escalar_operador(pedido, motivo, mensaje_cliente=None):
    """
    Marca el pedido para atención del operador.
    Opcionalmente manda un mensaje neutro al cliente.
    """
    try:
        from app import db, normalizar_telefono
        pedido.ml_mensajes_pendientes = True
        pedido.ml_mensajes_pendientes_count = (pedido.ml_mensajes_pendientes_count or 0) + 1
        pedido.ia_requiere_operador = True
        resumen_actual = (pedido.ia_resumen or "").strip()
        pedido.ia_resumen = f"{resumen_actual} | WA: {motivo}".strip(" |")
        db.session.commit()
        print(f"[WA] Pedido #{pedido.id} escalado: {motivo}")

        if mensaje_cliente:
            tel = normalizar_telefono(pedido.telefono)
            wa_enviar_texto(tel, mensaje_cliente)
    except Exception as e:
        print("[WA] Error escalando:", e)


def _es_afirmativo(texto):
    texto = texto.lower().strip()
    return any(x in texto for x in [
        "si", "sí", "ok", "dale", "confirmo", "confirmado", "correcto",
        "exacto", "perfecto", "claro", "obvio", "de una", "va", "bueno",
        "está bien", "esta bien", "todo bien", "listo", "ya", "por supuesto",
    ])


def _es_negativo(texto):
    texto = texto.lower().strip()
    return any(x in texto for x in [
        "no", "nope", "nel", "para nada", "negativo", "no gracias",
        "no me interesa", "no quiero", "paso", "por ahora no",
    ])


def _pregunta_precio(texto):
    texto = texto.lower().strip()
    return any(x in texto for x in [
        "cuanto", "cuánto", "precio", "sale", "cuesta", "valor", "costo", "plata",
    ])


def _pregunta_cantidad(texto):
    numeros = re.findall(r'\b([1-9][0-9]?)\b', texto)
    return int(numeros[0]) if numeros else None


def _es_queja_o_problema(texto):
    texto = texto.lower()
    return any(x in texto for x in [
        "reclamo", "queja", "problema", "no llegó", "no llego", "no recibi",
        "no recibí", "cancelar", "cancelación", "devolucion", "devolución",
        "estafa", "mentira", "mal", "roto", "defecto", "incompleto",
        "no funciona", "tarde", "demora", "donde esta", "dónde está",
    ])


# ─────────────────────────────────────────────
# FLUJO 1 — CONFIRMACIÓN DE SUCURSAL (Caso A)
# Datos completos + sucursal definida
# ─────────────────────────────────────────────

def wa_enviar_confirmacion_sucursal(pedido):
    """
    Primer mensaje al cliente cuando todo está listo para despachar.
    Reemplaza whatsapp_link_pedido.
    """
    from app import normalizar_telefono
    tel = normalizar_telefono(pedido.telefono)
    if not tel:
        return False

    nombre = (pedido.nombre or "").split()[0] or "Cliente"
    sucursal = pedido.sucursal_nombre or ""
    direccion = pedido.direccion or ""

    texto = (
        f"¡Hola {nombre}! 👋 Te escribo desde Fierro 100% Argento.\n\n"
        f"Quiero confirmarte el despacho de tu compra, así que acá te paso el detalle:\n\n"
        f"Tu pedido se despacha a:\n"
        f"📍 {sucursal}\n"
        f"📌 {direccion}\n\n"
        f"¿Confirmás que esa es la sucursal que elegiste?"
    )

    # Guardar estado en el pedido
    _guardar_estado_wa(pedido, "esperando_confirmacion_sucursal", tel)
    return wa_enviar_texto(tel, texto)


def wa_procesar_respuesta_confirmacion(pedido, texto_cliente):
    """
    Procesa la respuesta del cliente al mensaje de confirmación de sucursal.
    """
    from app import normalizar_telefono
    tel = normalizar_telefono(pedido.telefono)
    nombre = (pedido.nombre or "").split()[0] or "Cliente"

    if _es_queja_o_problema(texto_cliente):
        _escalar_operador(
            pedido, "Queja o problema en confirmación de sucursal",
            "Entendé tu consulta, dejame derivarte con un operador para que te ayude mejor 😊"
        )
        return

    if _es_afirmativo(texto_cliente):
        # Confirma sucursal → mensaje de seguimiento pendiente → cross-sell
        wa_enviar_texto(
            tel,
            "¡Perfecto! Solo nos resta pasarte el número de seguimiento "
            "para que puedas ver cómo va tu pedido de manera online 😊"
        )
        _guardar_estado_wa(pedido, "sucursal_confirmada", tel)
        # Iniciar cross-sell si corresponde
        wa_iniciar_cross_sell(pedido)
        return

    if _es_negativo(texto_cliente) or "otra sucursal" in texto_cliente.lower() or "cambiar" in texto_cliente.lower():
        # Quiere cambiar de sucursal → operador sin mensaje al cliente
        _escalar_operador(pedido, "Cliente quiere cambiar de sucursal")
        return

    if "domicilio" in texto_cliente.lower() or "casa" in texto_cliente.lower():
        # Quiere envío a domicilio
        wa_enviar_texto(
            tel,
            "Sí, correcto, el envío es sin cargo tal como está en la descripción de tu compra. "
            "Solo nos resta confirmarte el despacho para no errarle en nada "
            "y que recibas correctamente tu compra 😊"
        )
        return

    if "sin cargo" in texto_cliente.lower() or "gratis" in texto_cliente.lower() or "pagar" in texto_cliente.lower():
        wa_enviar_texto(
            tel,
            "Sí, correcto, el envío es sin cargo tal como está en la descripción de tu compra. "
            "Solo nos resta confirmarte el despacho para no errarle en nada "
            "y que recibas correctamente tu compra 😊"
        )
        return

    if any(x in texto_cliente.lower() for x in ["quien", "quién", "qué es", "que es", "no compré", "no compre", "equivocado"]):
        # Desconfianza o número equivocado
        from app import normalizar_telefono
        skus = _skus_str(pedido)
        fecha = pedido.fecha.strftime("%d/%m/%Y") if pedido.fecha else ""
        wa_enviar_texto(
            tel,
            f"Somos Fierro 100% Argento, la tienda donde realizaste tu compra 😊 "
            f"Te escribimos para coordinar el despacho de tu {skus} "
            f"{'que adquiriste el ' + fecha if fecha else ''}. "
            f"Cualquier duda estamos acá."
        )
        return

    # Respuesta no reconocida → IA intenta resolver o escala
    _wa_responder_con_ia(pedido, texto_cliente, tel)


# ─────────────────────────────────────────────
# FLUJO 2 — RECOLECCIÓN DE DATOS (Caso B)
# Solo tiene teléfono, faltan datos
# ─────────────────────────────────────────────

def wa_enviar_solicitud_datos(pedido, faltantes):
    """
    Primer mensaje cuando el cliente dio solo el teléfono por ML
    y faltan datos para procesar el despacho.
    """
    from app import normalizar_telefono
    tel = normalizar_telefono(pedido.telefono)
    if not tel:
        return False

    nombre = (pedido.nombre or "").split()[0] if pedido.nombre else ""
    saludo = f"¡Hola {nombre}! 👋 " if nombre else "¡Hola! 👋 "

    campos_amigables = {
        "nombre":         "nombre y apellido",
        "apellido":       "apellido",
        "dni":            "DNI",
        "direccion":      "dirección",
        "localidad":      "localidad",
        "codigo_postal":  "código postal",
    }

    faltantes_str = "\n".join(
        f"• {campos_amigables.get(f, f)}" for f in faltantes
    )

    texto = (
        f"{saludo}Te escribo desde Fierro 100% Argento para coordinar "
        f"el despacho de tu compra.\n\n"
        f"Para poder avanzar con el envío necesito confirmar algunos datos:\n\n"
        f"{faltantes_str}\n\n"
        f"¿Me los podés confirmar por acá? 😊"
    )

    _guardar_estado_wa(pedido, "esperando_datos", tel)
    return wa_enviar_texto(tel, texto)


def wa_procesar_datos_recibidos(pedido, texto_cliente):
    """
    Procesa los datos que manda el cliente en respuesta a la solicitud.
    Reutiliza la IA de ML para extraer los datos del texto.
    """
    from app import (
        normalizar_telefono, ia_analizar_datos_cliente_ml_acordas,
        ia_guardar_resultado_recolector, ia_faltantes_pedido,
        ia_datos_previos_pedido,
    )
    tel = normalizar_telefono(pedido.telefono)

    if _es_queja_o_problema(texto_cliente):
        _escalar_operador(
            pedido, "Queja durante recolección de datos",
            "Entendé tu consulta, dejame derivarte con un operador para que te ayude mejor 😊"
        )
        return

    # Reutilizar IA de ML para extraer datos
    resultado = ia_analizar_datos_cliente_ml_acordas(
        texto_cliente,
        ia_datos_previos_pedido(pedido)
    )
    ia_guardar_resultado_recolector(pedido, texto_cliente, resultado)

    # Chequear si ya están completos
    faltantes = ia_faltantes_pedido(pedido)
    if not faltantes:
        # Datos completos → avanzar al flujo de confirmación de sucursal
        from .flows import wa_enviar_confirmacion_sucursal
        wa_enviar_confirmacion_sucursal(pedido)
    else:
        # Siguen faltando datos → pedir solo los que faltan
        wa_enviar_texto(
            tel,
            f"¡Gracias! Solo me falta confirmar:\n\n" +
            "\n".join(f"• {f}" for f in faltantes) +
            "\n\n¿Me los podés pasar? 😊"
        )


# ─────────────────────────────────────────────
# FLUJO 3 — CROSS-SELL
# ─────────────────────────────────────────────

def wa_iniciar_cross_sell(pedido):
    """
    Arranca el flujo de cross-sell si hay productos para ofrecer.
    Se llama después de confirmar la sucursal.
    """
    from app import normalizar_telefono
    tel = normalizar_telefono(pedido.telefono)
    productos = obtener_productos_a_ofrecer(pedido)

    if not productos:
        return

    # Ofrecer el primer producto
    primer_sku = productos[0]
    _guardar_estado_wa(pedido, f"cross_sell:{primer_sku}:0", tel)
    wa_ofrecer_producto(tel, primer_sku)


def wa_procesar_respuesta_cross_sell(pedido, texto_cliente, sku_actual, indice_actual):
    """
    Procesa la respuesta del cliente durante el flujo de cross-sell.
    """
    from app import normalizar_telefono
    tel = normalizar_telefono(pedido.telefono)
    productos = obtener_productos_a_ofrecer(pedido)

    if _es_queja_o_problema(texto_cliente):
        _escalar_operador(
            pedido, "Queja durante cross-sell",
            "Entendé tu consulta, dejame derivarte con un operador para que te ayude mejor 😊"
        )
        return

    # Pregunta precio o confirma interés
    if _pregunta_precio(texto_cliente) or _es_afirmativo(texto_cliente):
        cantidad = _pregunta_cantidad(texto_cliente) or 1
        wa_responder_precio(tel, sku_actual, cantidad)
        _guardar_estado_wa(pedido, f"cross_sell:{sku_actual}:precio_enviado:{cantidad}", tel)
        return

    # Confirma compra después de ver precio
    if "precio_enviado" in _obtener_estado_wa(pedido):
        if _es_afirmativo(texto_cliente):
            cantidad = _pregunta_cantidad(texto_cliente) or 1
            wa_escalar_venta_cerrada(pedido, sku_actual, cantidad)
            # Ofrecer siguiente producto si hay
            siguiente_idx = indice_actual + 1
            if siguiente_idx < len(productos):
                siguiente_sku = productos[siguiente_idx]
                _guardar_estado_wa(pedido, f"cross_sell:{siguiente_sku}:{siguiente_idx}", tel)
                wa_ofrecer_producto(tel, siguiente_sku)
            else:
                wa_cerrar_cross_sell(tel)
                _guardar_estado_wa(pedido, "cross_sell_cerrado", tel)
            return

    # No le interesa → siguiente producto
    if _es_negativo(texto_cliente):
        siguiente_idx = indice_actual + 1
        if siguiente_idx < len(productos):
            siguiente_sku = productos[siguiente_idx]
            _guardar_estado_wa(pedido, f"cross_sell:{siguiente_sku}:{siguiente_idx}", tel)
            wa_ofrecer_producto(tel, siguiente_sku)
        else:
            wa_cerrar_cross_sell(tel)
            _guardar_estado_wa(pedido, "cross_sell_cerrado", tel)
        return

    # Respuesta no reconocida → IA
    _wa_responder_con_ia(pedido, texto_cliente, tel)


# ─────────────────────────────────────────────
# FLUJO 4 — DESPACHO Y SEGUIMIENTO
# ─────────────────────────────────────────────

def wa_enviar_numero_seguimiento(pedido):
    """
    Manda el número de seguimiento cuando el pedido es despachado.
    Reemplaza whatsapp_link_despachado.
    """
    from app import normalizar_telefono
    tel = normalizar_telefono(pedido.telefono)
    if not tel:
        return False

    nombre = (pedido.nombre or "").split()[0] or "Cliente"
    seguimiento = (pedido.numero_seguimiento or "").strip()

    if not seguimiento:
        return False

    texto = (
        f"¡Hola {nombre}! 📦\n\n"
        f"Tu pedido ya fue despachado. Acá te paso el número de seguimiento "
        f"para que puedas ver cómo va tu envío de manera online:\n\n"
        f"🔍 *{seguimiento}*\n\n"
        f"Podés rastrearlo en la web de Vía Cargo. "
        f"Cualquier duda escribinos acá 😊"
    )

    return wa_enviar_texto(tel, texto)


def wa_enviar_listo_para_retirar(pedido):
    """
    Avisa que el pedido está listo para retirar.
    Reemplaza whatsapp_link_confirmar_entrega.
    """
    from app import normalizar_telefono
    tel = normalizar_telefono(pedido.telefono)
    if not tel:
        return False

    nombre = (pedido.nombre or "").split()[0] or "Cliente"

    texto = (
        f"¡Hola {nombre}! 🎉\n\n"
        f"Tu pedido está *listo para retirar* en:\n\n"
        f"📍 *{pedido.sucursal_nombre or 'la sucursal elegida'}*\n"
        f"📌 {pedido.direccion or ''}\n\n"
        f"¡Te esperamos! Ante cualquier duda escribinos acá 😊"
    )

    return wa_enviar_texto(tel, texto)


# ─────────────────────────────────────────────
# FLUJO 5 — POSTVENTA
# ─────────────────────────────────────────────

def wa_enviar_postventa(pedido):
    """
    Mensaje de postventa después de que el cliente retiró.
    Reemplaza whatsapp_link_postventa.
    """
    from app import normalizar_telefono
    tel = normalizar_telefono(pedido.telefono)
    if not tel:
        return False

    nombre = (pedido.nombre or "").split()[0] or "Cliente"

    texto = (
        f"¡Hola {nombre}! 👋\n\n"
        f"Vimos que ya recibiste tu parrilla. "
        f"Esperamos haber cumplido con tus expectativas, ¡gracias por confiar en nosotros! 🙌\n\n"
        f"Te dejamos algunos tips para que te dure muchos años:\n\n"
        f"• Evitá quemarla a fuego directo, ese calor puede doblar las varillas.\n"
        f"• Limpiala con un cepillo mientras está caliente, justo después de usarla.\n"
        f"• Usá la grasa del asado para pasarle y curarla; ayuda a evitar el óxido.\n"
        f"• Si queda al aire libre, podés pasarle aceite comestible con una esponja.\n\n"
        f"Si tenés alguna duda con el uso, escribinos.\n\n"
        f"Gracias nuevamente 😊\n"
        f"Y si querés, seguinos en Instagram para ver lo nuevo que vamos sumando:\n"
        f"https://www.instagram.com/fierroargento"
    )

    return wa_enviar_texto(tel, texto)


def wa_procesar_respuesta_postventa(pedido, texto_cliente):
    """Procesa respuestas al mensaje de postventa."""
    from app import normalizar_telefono
    tel = normalizar_telefono(pedido.telefono)

    if _es_queja_o_problema(texto_cliente):
        _escalar_operador(
            pedido, "Problema postventa",
            "Entendé tu consulta, dejame derivarte con un operador para que te ayude mejor 😊"
        )
        return

    if _es_afirmativo(texto_cliente) or "gracias" in texto_cliente.lower():
        wa_enviar_texto(tel, "¡Gracias a vos! Un placer 😊🔥")
        return

    # Cualquier otra cosa → IA o escala
    _wa_responder_con_ia(pedido, texto_cliente, tel)


# ─────────────────────────────────────────────
# RECORDATORIOS (sin respuesta del cliente)
# ─────────────────────────────────────────────

def wa_enviar_recordatorio_1(pedido):
    """Primer recordatorio a la hora sin respuesta."""
    from app import normalizar_telefono
    tel = normalizar_telefono(pedido.telefono)
    nombre = (pedido.nombre or "").split()[0] or ""
    saludo = f"Hola {nombre} 👋 " if nombre else "Hola 👋 "
    wa_enviar_texto(
        tel,
        f"{saludo}Solo quería asegurarme de que te haya llegado mi mensaje anterior. "
        f"Quedamos a disposición para confirmar el despacho de tu parrilla 😊"
    )


def wa_enviar_recordatorio_2(pedido):
    """Segundo y último recordatorio a las 3 horas sin respuesta."""
    from app import normalizar_telefono
    tel = normalizar_telefono(pedido.telefono)
    nombre = (pedido.nombre or "").split()[0] or ""
    saludo = f"Hola {nombre} 👋 " if nombre else "Hola 👋 "
    wa_enviar_texto(
        tel,
        f"{saludo}Te escribimos por última vez para confirmar el despacho de tu parrilla. "
        f"Necesitamos tu confirmación para poder avanzar con el envío. "
        f"Si tenés alguna duda o inconveniente podés escribirnos acá 😊"
    )


# ─────────────────────────────────────────────
# HELPERS INTERNOS
# ─────────────────────────────────────────────

def _skus_str(pedido):
    """Devuelve descripción legible de los productos del pedido."""
    items = pedido.items or []
    if not items:
        return "pedido"
    descripciones = [str(getattr(i, "descripcion", "") or getattr(i, "sku", "") or "producto") for i in items[:2]]
    return " y ".join(descripciones)


def _guardar_estado_wa(pedido, estado, tel=None):
    """Guarda el estado de la conversación WhatsApp en el pedido."""
    try:
        from app import db
        pedido.wa_estado = estado
        pedido.wa_ultimo_contacto = datetime.utcnow()
        db.session.commit()
    except Exception as e:
        print("[WA] Error guardando estado:", e)


def _obtener_estado_wa(pedido):
    return str(getattr(pedido, "wa_estado", "") or "")


def _wa_responder_con_ia(pedido, texto_cliente, tel):
    """Último recurso: IA responde o escala."""
    try:
        from app import ia_llamar_openai_chat
        prompt = f"""
Sos el asistente de atención al cliente de Fierro 100% Argento, empresa que vende parrillas.
Respondé de forma amable, breve y en español rioplatense.

Estado del pedido: {pedido.estado or 'En proceso'}
Sucursal de retiro: {pedido.sucursal_nombre or 'No asignada aún'}

Mensaje del cliente: \"\"\"{texto_cliente}\"\"\"

REGLAS:
- Si es sobre el producto (parrillas, medidas, materiales, garantía) respondé con info general.
- Si es sobre demoras: el plazo habitual es 3 a 5 días hábiles desde el despacho.
- Si es queja, reclamo, cancelación o algo que no podés resolver → respondé que un operador
  se va a comunicar y al final escribí exactamente: ESCALAR
- Nunca confirmes fechas exactas ni hagas promesas de entrega.
- Respondé solo el mensaje para el cliente.
"""
        respuesta = ia_llamar_openai_chat(prompt)
        if "ESCALAR" in (respuesta or ""):
            respuesta = respuesta.replace("ESCALAR", "").strip()
            _escalar_operador(pedido, f"IA no pudo resolver: {texto_cliente[:80]}")
        if respuesta:
            wa_enviar_texto(tel, respuesta)
    except Exception as e:
        print("[WA] Error IA:", e)
        _escalar_operador(
            pedido, "Error IA",
            "Entendé tu consulta, dejame derivarte con un operador para que te ayude mejor 😊"
        )
