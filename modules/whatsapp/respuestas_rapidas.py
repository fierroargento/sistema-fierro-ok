CATEGORIA_DEFAULT = "General"


def _normalizar_texto(valor):
    return str(valor or "").strip()


def _normalizar_orden(valor):
    try:
        return int(valor)
    except Exception:
        return 100


def validar_respuesta_rapida_payload(titulo, texto):
    titulo = _normalizar_texto(titulo)
    texto = _normalizar_texto(texto)

    if not titulo:
        return False, "El título no puede quedar vacío."

    if not texto:
        return False, "El texto no puede quedar vacío."

    if len(titulo) > 120:
        return False, "El título no puede superar 120 caracteres."

    if len(texto) > 2000:
        return False, "El texto no puede superar 2000 caracteres."

    return True, ""


def listar_respuestas_rapidas_wa(modelo, empresa_id=1, incluir_inactivas=True):
    query = modelo.query.filter_by(empresa_id=empresa_id)

    if not incluir_inactivas:
        query = query.filter_by(activa=True)

    return (
        query
        .order_by(modelo.activa.desc(), modelo.orden.asc(), modelo.titulo.asc())
        .all()
    )


def obtener_respuestas_activas_wa(modelo, empresa_id=1):
    return listar_respuestas_rapidas_wa(
        modelo,
        empresa_id=empresa_id,
        incluir_inactivas=False,
    )


def crear_respuesta_rapida_wa(
    modelo,
    db,
    *,
    empresa_id=1,
    titulo="",
    texto="",
    categoria="",
    orden=100,
    creado_por="",
    imagen_url="",
    imagen_public_id="",
    imagen_nombre="",
):
    ok, error = validar_respuesta_rapida_payload(titulo, texto)
    if not ok:
        return False, error, None

    respuesta = modelo(
        empresa_id=empresa_id,
        titulo=_normalizar_texto(titulo),
        texto=_normalizar_texto(texto),
        categoria=_normalizar_texto(categoria) or CATEGORIA_DEFAULT,
        orden=_normalizar_orden(orden),
        activa=True,
        creado_por=_normalizar_texto(creado_por),
        imagen_url=_normalizar_texto(imagen_url),
        imagen_public_id=_normalizar_texto(imagen_public_id),
        imagen_nombre=_normalizar_texto(imagen_nombre),
    )

    db.session.add(respuesta)
    db.session.commit()

    return True, "Respuesta rápida creada correctamente.", respuesta


def actualizar_respuesta_rapida_wa(
    respuesta,
    db,
    *,
    titulo="",
    texto="",
    categoria="",
    orden=100,
    imagen_url=None,
    imagen_public_id=None,
    imagen_nombre=None,
):
    ok, error = validar_respuesta_rapida_payload(titulo, texto)
    if not ok:
        return False, error

    respuesta.titulo = _normalizar_texto(titulo)
    respuesta.texto = _normalizar_texto(texto)
    respuesta.categoria = _normalizar_texto(categoria) or CATEGORIA_DEFAULT
    respuesta.orden = _normalizar_orden(orden)

    if imagen_url is not None:
        respuesta.imagen_url = _normalizar_texto(imagen_url)

    if imagen_public_id is not None:
        respuesta.imagen_public_id = _normalizar_texto(imagen_public_id)

    if imagen_nombre is not None:
        respuesta.imagen_nombre = _normalizar_texto(imagen_nombre)

    db.session.commit()

    return True, "Respuesta rápida actualizada correctamente."


def toggle_respuesta_rapida_wa(respuesta, db):
    respuesta.activa = not bool(respuesta.activa)
    db.session.commit()

    estado = "activada" if respuesta.activa else "desactivada"
    return True, f"Respuesta rápida {estado} correctamente."

ALLOWED_IMAGEN_WA_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_IMAGEN_WA_BYTES = 5 * 1024 * 1024


def imagen_manual_wa_es_valida(archivo):
    """
    Valida una imagen manual antes de subirla/enviarla por WhatsApp.

    APB:
    - Solo imágenes.
    - Tamaño controlado.
    - No PDFs/documentos en este flujo.
    """
    if not archivo or not getattr(archivo, "filename", ""):
        return True, ""

    mimetype = str(getattr(archivo, "mimetype", "") or "").lower().strip()

    if mimetype not in ALLOWED_IMAGEN_WA_MIME_TYPES:
        return False, "Solo se permiten imágenes JPG, PNG o WEBP para enviar por WhatsApp."

    try:
        archivo.stream.seek(0, 2)
        size = archivo.stream.tell()
        archivo.stream.seek(0)
    except Exception:
        size = 0

    if size and size > MAX_IMAGEN_WA_BYTES:
        return False, "La imagen no puede superar 5 MB."

    return True, ""


def subir_imagen_manual_wa_cloudinary(archivo, *, pedido_id="", usuario=""):
    """
    Sube imagen manual del operador a Cloudinary y devuelve metadata segura.
    No guarda claves ni depende de app.py.
    """
    if not archivo or not getattr(archivo, "filename", ""):
        return {
            "url": "",
            "public_id": "",
            "nombre": "",
        }

    ok, error = imagen_manual_wa_es_valida(archivo)
    if not ok:
        raise ValueError(error)

    import cloudinary.uploader

    nombre_original = str(archivo.filename or "").strip()
    carpeta = f"sistema_fierro/wa_operador/pedido_{pedido_id or 'sin_pedido'}"

    resultado = cloudinary.uploader.upload(
        archivo,
        folder=carpeta,
        resource_type="image",
        use_filename=True,
        unique_filename=True,
        overwrite=False,
        context={
            "pedido_id": str(pedido_id or ""),
            "usuario": str(usuario or ""),
            "origen": "operador_manual_wa",
        },
    )

    return {
        "url": resultado.get("secure_url", ""),
        "public_id": resultado.get("public_id", ""),
        "nombre": nombre_original,
    }