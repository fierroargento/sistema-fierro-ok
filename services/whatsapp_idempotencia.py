"""
services/whatsapp_idempotencia.py
────────────────────────────────
Protección contra envíos manuales duplicados por WhatsApp.

APB:
- Un doble click, refresh o doble submit NO debe generar dos mensajes reales a Meta.
- La regla es defensiva y acotada: mismo pedido + mismo texto + operador + ventana corta.
- No depende del frontend.
"""

from datetime import datetime, timedelta


def normalizar_texto_mensaje_manual(texto):
    """
    Normaliza texto para comparar duplicados exactos razonables.
    No cambia el contenido comercial; solo evita diferencias por espacios/saltos.
    """
    texto = str(texto or "").strip()
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")

    lineas = [
        " ".join(linea.split())
        for linea in texto.split("\n")
    ]

    return "\n".join(linea for linea in lineas if linea).strip()


def mensaje_texto_duplicado_en_lista(
    mensajes,
    texto,
    ahora=None,
    ventana_segundos=10,
):
    """
    Evalúa si en una lista de mensajes ya existe el mismo texto dentro
    de la ventana de protección.
    """
    texto_normalizado = normalizar_texto_mensaje_manual(texto)

    if not texto_normalizado:
        return False

    ahora = ahora or datetime.utcnow()
    desde = ahora - timedelta(seconds=ventana_segundos)

    for mensaje in mensajes or []:
        fecha = getattr(mensaje, "fecha", None)
        if not fecha:
            continue

        if fecha < desde:
            continue

        texto_mensaje = normalizar_texto_mensaje_manual(
            getattr(mensaje, "texto", "")
        )

        if texto_mensaje == texto_normalizado:
            return True

    return False


def ya_existe_mensaje_operador_reciente(
    WhatsAppMensaje,
    pedido,
    texto,
    ventana_segundos=10,
):
    """
    Consulta DB para evitar duplicados de envío manual WA.

    Devuelve True si el operador ya envió el mismo texto para el mismo pedido
    dentro de los últimos N segundos.
    """
    if not WhatsAppMensaje or not pedido:
        return False

    texto_normalizado = normalizar_texto_mensaje_manual(texto)

    if not texto_normalizado:
        return False

    pedido_id = getattr(pedido, "id", None)
    if not pedido_id:
        return False

    ahora = datetime.utcnow()
    desde = ahora - timedelta(seconds=ventana_segundos)

    mensajes_recientes = (
        WhatsAppMensaje.query
        .filter(
            WhatsAppMensaje.pedido_id == pedido_id,
            WhatsAppMensaje.direccion == "out",
            WhatsAppMensaje.autor == "operador",
            WhatsAppMensaje.fecha >= desde,
        )
        .order_by(WhatsAppMensaje.fecha.desc())
        .limit(10)
        .all()
    )

    return mensaje_texto_duplicado_en_lista(
        mensajes_recientes,
        texto_normalizado,
        ahora=ahora,
        ventana_segundos=ventana_segundos,
    )