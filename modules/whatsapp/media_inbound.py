import os
import tempfile

import requests
import cloudinary.uploader


ALLOWED_WA_INBOUND_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}

MAX_WA_INBOUND_MEDIA_BYTES = 10 * 1024 * 1024


def _normalizar_texto(valor):
    return str(valor or "").strip()


def _obtener_token_whatsapp():
    """
    Busca el token de WhatsApp en variables habituales.

    APB:
    - No hardcodear token.
    - No imprimir token.
    """
    for clave in [
        "WHATSAPP_ACCESS_TOKEN",
        "WA_ACCESS_TOKEN",
        "META_ACCESS_TOKEN",
        "WHATSAPP_TOKEN",
    ]:
        valor = os.getenv(clave, "").strip()
        if valor:
            return valor

    return ""


def extraer_media_desde_mensaje_meta(msg):
    """
    Extrae datos básicos de un mensaje Meta tipo image/document.

    Devuelve None si no es media soportada.
    """
    tipo = _normalizar_texto((msg or {}).get("type")).lower()

    if tipo not in ["image", "document"]:
        return None

    bloque = (msg or {}).get(tipo) or {}

    media_id = _normalizar_texto(bloque.get("id"))
    mime_type = _normalizar_texto(bloque.get("mime_type")).lower()
    caption = _normalizar_texto(bloque.get("caption"))
    filename = _normalizar_texto(bloque.get("filename"))

    if not filename:
        if tipo == "image":
            filename = "imagen_whatsapp"
        elif mime_type == "application/pdf":
            filename = "documento_whatsapp.pdf"
        else:
            filename = "archivo_whatsapp"

    if not media_id:
        return None

    return {
        "tipo": tipo,
        "media_id": media_id,
        "mime_type": mime_type,
        "caption": caption,
        "filename": filename,
    }


def validar_media_inbound(mime_type, size_bytes=0):
    mime_type = _normalizar_texto(mime_type).lower()

    if mime_type not in ALLOWED_WA_INBOUND_MIME_TYPES:
        return False, f"Tipo de archivo no permitido: {mime_type or 'sin tipo'}"

    try:
        size_bytes = int(size_bytes or 0)
    except Exception:
        size_bytes = 0

    if size_bytes and size_bytes > MAX_WA_INBOUND_MEDIA_BYTES:
        return False, "El archivo recibido supera el máximo permitido de 10 MB."

    return True, ""


def obtener_url_temporal_media_meta(media_id, access_token=None):
    """
    Consulta a Meta por la URL temporal de descarga del media_id.
    """
    media_id = _normalizar_texto(media_id)
    access_token = access_token or _obtener_token_whatsapp()

    if not media_id:
        raise ValueError("media_id vacío.")

    if not access_token:
        raise RuntimeError("No hay token WhatsApp configurado para descargar media.")

    url = f"https://graph.facebook.com/v20.0/{media_id}"

    resp = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        timeout=20,
    )

    if resp.status_code >= 400:
        raise RuntimeError(f"Meta media lookup error {resp.status_code}: {resp.text[:300]}")

    data = resp.json() or {}
    media_url = _normalizar_texto(data.get("url"))
    mime_type = _normalizar_texto(data.get("mime_type")).lower()
    file_size = data.get("file_size") or 0

    if not media_url:
        raise RuntimeError("Meta no devolvió URL temporal para media.")

    return {
        "url": media_url,
        "mime_type": mime_type,
        "file_size": file_size,
    }


def descargar_media_meta(media_url, access_token=None):
    """
    Descarga el archivo desde la URL temporal de Meta.
    """
    access_token = access_token or _obtener_token_whatsapp()

    if not access_token:
        raise RuntimeError("No hay token WhatsApp configurado para descargar media.")

    resp = requests.get(
        media_url,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        timeout=30,
    )

    if resp.status_code >= 400:
        raise RuntimeError(f"Meta media download error {resp.status_code}: {resp.text[:300]}")

    contenido = resp.content or b""
    if not contenido:
        raise RuntimeError("Meta devolvió archivo vacío.")

    if len(contenido) > MAX_WA_INBOUND_MEDIA_BYTES:
        raise RuntimeError("El archivo recibido supera el máximo permitido de 10 MB.")

    return contenido


def subir_media_inbound_cloudinary(
    contenido,
    *,
    pedido_id="",
    telefono="",
    filename="",
    tipo="",
    mime_type="",
):
    """
    Sube media recibida a Cloudinary.

    APB:
    - resource_type auto para PDF/imágenes.
    - carpeta separada para media entrante.
    """
    if not contenido:
        raise ValueError("Contenido vacío para subir a Cloudinary.")

    filename = _normalizar_texto(filename) or "archivo_whatsapp"
    tipo = _normalizar_texto(tipo) or "media"
    pedido_id = _normalizar_texto(pedido_id) or "sin_pedido"

    suffix = os.path.splitext(filename)[1] or ""
    temp_path = ""

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(contenido)
            temp_path = tmp.name

        resultado = cloudinary.uploader.upload(
            temp_path,
            folder=f"sistema_fierro/wa_inbound/pedido_{pedido_id}",
            resource_type="auto",
            use_filename=True,
            unique_filename=True,
            overwrite=False,
            context={
                "pedido_id": str(pedido_id),
                "telefono": str(telefono or ""),
                "tipo": str(tipo or ""),
                "mime_type": str(mime_type or ""),
                "origen": "whatsapp_cliente",
            },
        )

        return {
            "url": resultado.get("secure_url", ""),
            "public_id": resultado.get("public_id", ""),
            "size_bytes": len(contenido),
        }

    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except Exception:
                pass


def procesar_media_inbound_whatsapp(
    *,
    msg,
    pedido,
    telefono,
    WhatsAppMediaRecibida,
    db,
):
    """
    Procesa un mensaje entrante image/document:
    - extrae media_id,
    - descarga desde Meta,
    - valida,
    - sube a Cloudinary,
    - registra WhatsAppMediaRecibida.

    Devuelve dict con texto_historial y metadata.
    """
    media = extraer_media_desde_mensaje_meta(msg)
    if not media:
        return None

    lookup = obtener_url_temporal_media_meta(media["media_id"])
    mime_type = media.get("mime_type") or lookup.get("mime_type") or ""
    size_meta = lookup.get("file_size") or 0

    ok, error = validar_media_inbound(mime_type, size_meta)
    if not ok:
        raise ValueError(error)

    contenido = descargar_media_meta(lookup["url"])

    ok, error = validar_media_inbound(mime_type, len(contenido))
    if not ok:
        raise ValueError(error)

    subida = subir_media_inbound_cloudinary(
        contenido,
        pedido_id=getattr(pedido, "id", "") if pedido else "",
        telefono=telefono,
        filename=media.get("filename", ""),
        tipo=media.get("tipo", ""),
        mime_type=mime_type,
    )

    tipo = media.get("tipo") or ""

    if tipo == "image":
        etiqueta = "Imagen recibida por WhatsApp"
    elif mime_type == "application/pdf":
        etiqueta = "PDF recibido por WhatsApp"
    else:
        etiqueta = "Archivo recibido por WhatsApp"

    nombre = media.get("filename") or ""

    texto_historial = etiqueta

    if nombre:
        texto_historial += f"\n{nombre}"

    if media.get("caption"):
        texto_historial += f"\n\nComentario del cliente:\n{media.get('caption')}"

    registro = WhatsAppMediaRecibida(
        empresa_id=1,
        pedido_id=getattr(pedido, "id", None),
        telefono=str(telefono or ""),
        message_id_meta=str((msg or {}).get("id") or ""),
        media_id_meta=media.get("media_id", ""),
        tipo=tipo,
        mime_type=mime_type,
        filename=media.get("filename", ""),
        caption=media.get("caption", ""),
        cloudinary_url=subida.get("url", ""),
        cloudinary_public_id=subida.get("public_id", ""),
        size_bytes=subida.get("size_bytes") or len(contenido),
        estado_scan="pendiente",
        error="",
    )

    db.session.add(registro)
    db.session.commit()

    return {
        "registro": registro,
        "texto_historial": texto_historial,
        "cloudinary_url": subida.get("url", ""),
        "tipo": tipo,
        "mime_type": mime_type,
        "filename": media.get("filename", ""),
        "caption": media.get("caption", ""),
    }