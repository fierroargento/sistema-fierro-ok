"""Carga segura de comprobantes asociados a pagos productivos."""

from services.seguridad_entorno import exigir_conexion_externa, exigir_efecto_externo
from services.almacenamiento_archivos import (
    almacenamiento_local_habilitado,
    guardar_archivo_local,
)

EXTENSIONES_PERMITIDAS = {"pdf", "png", "jpg", "jpeg", "webp"}
TAMANO_MAXIMO = 10 * 1024 * 1024


def guardar_comprobante_pago(
    archivo, *, organizacion_id=None, unidad_negocio_id=None,
):
    """Guarda un PDF o imagen en Cloudinary y devuelve su URL segura."""
    if archivo is None or not getattr(archivo, "filename", ""):
        return ""
    nombre = archivo.filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    extension = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if extension not in EXTENSIONES_PERMITIDAS:
        raise ValueError("El comprobante debe ser PDF, PNG, JPG o WEBP.")
    if almacenamiento_local_habilitado():
        resultado = guardar_archivo_local(
            archivo,
            organizacion_id=organizacion_id,
            unidad_negocio_id=unidad_negocio_id,
            espacio="costos_comprobantes_pago",
            limite_bytes=TAMANO_MAXIMO,
            extensiones_permitidas=EXTENSIONES_PERMITIDAS,
            validar_imagen=extension != "pdf",
        )
        return resultado["url"]
    if not organizacion_id or not unidad_negocio_id:
        raise ValueError("El comprobante requiere organización y unidad.")
    exigir_conexion_externa("CLOUDINARY", "Carga de comprobante de pago")
    exigir_efecto_externo("CLOUDINARY", "Carga de comprobante de pago")

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
        folder=(
            f"costos_productivos/{int(organizacion_id)}/"
            f"{int(unidad_negocio_id)}/comprobantes_pago"
        ),
        use_filename=True,
        unique_filename=True,
        overwrite=False,
    )
    url = (resultado.get("secure_url") or "").strip()
    if not url:
        raise ValueError("No se pudo guardar el comprobante. Volvé a intentar.")
    return url
