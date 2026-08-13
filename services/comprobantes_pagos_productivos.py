"""Carga segura de comprobantes asociados a pagos productivos."""

EXTENSIONES_PERMITIDAS = {"pdf", "png", "jpg", "jpeg", "webp"}
TAMANO_MAXIMO = 10 * 1024 * 1024


def guardar_comprobante_pago(archivo):
    """Guarda un PDF o imagen en Cloudinary y devuelve su URL segura."""
    if archivo is None or not getattr(archivo, "filename", ""):
        return ""
    nombre = archivo.filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    extension = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if extension not in EXTENSIONES_PERMITIDAS:
        raise ValueError("El comprobante debe ser PDF, PNG, JPG o WEBP.")

    contenido = archivo.read(TAMANO_MAXIMO + 1)
    if len(contenido) > TAMANO_MAXIMO:
        raise ValueError("El comprobante no puede superar los 10 MB.")
    if not contenido:
        raise ValueError("El comprobante está vacío.")
    archivo.stream.seek(0)

    import cloudinary.uploader

    resultado = cloudinary.uploader.upload(
        archivo,
        resource_type="auto",
        folder="costos_productivos/comprobantes_pago",
        use_filename=True,
        unique_filename=True,
        overwrite=False,
    )
    url = (resultado.get("secure_url") or "").strip()
    if not url:
        raise ValueError("No se pudo guardar el comprobante. Volvé a intentar.")
    return url
