"""Almacenamiento local aislado para UAT, sin servicios externos."""

from io import BytesIO
import os
from pathlib import Path
from uuid import uuid4

from PIL import Image
from werkzeug.utils import secure_filename


def almacenamiento_local_habilitado():
    return os.getenv("ALMACENAMIENTO_ARCHIVOS", "").strip().lower() == "local_aislado"


def raiz_local_aislada():
    raiz = Path(os.getenv("STAGING_UPLOAD_ROOT", "").strip())
    if not raiz.is_absolute():
        raise RuntimeError("STAGING_UPLOAD_ROOT debe ser una ruta absoluta.")
    return raiz.resolve()


def guardar_imagen_local(archivo, *, organizacion_id, espacio, limite_bytes):
    """Valida y guarda una imagen con nombre no controlado por el usuario."""
    nombre = secure_filename(str(getattr(archivo, "filename", "") or ""))
    extension = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if extension not in {"jpg", "jpeg", "png", "webp"}:
        raise ValueError("Las imágenes deben ser JPG, PNG o WEBP.")
    contenido = archivo.read(limite_bytes + 1)
    if not contenido or len(contenido) > limite_bytes:
        raise ValueError("La imagen está vacía o supera el tamaño permitido.")
    try:
        with Image.open(BytesIO(contenido)) as imagen:
            imagen.verify()
    except Exception as error:
        raise ValueError("El archivo no contiene una imagen válida.") from error

    raiz = raiz_local_aislada()
    espacio_seguro = secure_filename(str(espacio or "general")) or "general"
    directorio = (raiz / f"organizacion_{int(organizacion_id)}" / espacio_seguro).resolve()
    if raiz not in directorio.parents:
        raise RuntimeError("Ruta de almacenamiento fuera del espacio aislado.")
    directorio.mkdir(parents=True, exist_ok=True)
    nombre_guardado = f"{uuid4().hex}.{extension}"
    destino = directorio / nombre_guardado
    with destino.open("xb") as salida:
        salida.write(contenido)
    archivo.stream.seek(0)
    ruta_relativa = f"{espacio_seguro}/{nombre_guardado}"
    return {
        "url": f"/archivos-uat/{int(organizacion_id)}/{ruta_relativa}",
        "public_id": f"local:{int(organizacion_id)}:{ruta_relativa}",
        "principal": False,
    }
