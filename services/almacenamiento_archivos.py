"""Almacenamiento local aislado para UAT, sin servicios externos."""

from io import BytesIO
import os
from pathlib import Path
import re
from uuid import uuid4

from PIL import Image


def almacenamiento_local_habilitado():
    return os.getenv("ALMACENAMIENTO_ARCHIVOS", "").strip().lower() == "local_aislado"


def raiz_local_aislada():
    raiz = Path(os.getenv("STAGING_UPLOAD_ROOT", "").strip())
    if not raiz.is_absolute():
        raise RuntimeError("STAGING_UPLOAD_ROOT debe ser una ruta absoluta.")
    raiz = raiz.resolve()
    if raiz == Path(raiz.anchor):
        raise RuntimeError("STAGING_UPLOAD_ROOT no puede ser la raíz del sistema.")
    return raiz


def _nombre_seguro(valor, default="archivo"):
    nombre = str(valor or "").replace("\\", "/").rsplit("/", 1)[-1]
    nombre = re.sub(r"[^A-Za-z0-9._-]+", "_", nombre).strip("._")
    return nombre[:180] or default


def _identidad_almacenamiento(organizacion_id, unidad_negocio_id):
    try:
        organizacion_id = int(organizacion_id)
        unidad_negocio_id = int(unidad_negocio_id)
    except (TypeError, ValueError) as error:
        raise ValueError("El archivo requiere organización y unidad válidas.") from error
    if organizacion_id <= 0 or unidad_negocio_id <= 0:
        raise ValueError("El archivo requiere organización y unidad válidas.")
    return organizacion_id, unidad_negocio_id


def guardar_archivo_local(
    archivo, *, organizacion_id, unidad_negocio_id, espacio, limite_bytes,
    extensiones_permitidas, validar_imagen=False,
):
    """Valida y guarda un archivo dentro del espacio aislado del tenant."""
    organizacion_id, unidad_negocio_id = _identidad_almacenamiento(
        organizacion_id, unidad_negocio_id,
    )
    nombre = _nombre_seguro(getattr(archivo, "filename", ""))
    extension = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    permitidas = {str(valor).lower() for valor in extensiones_permitidas}
    if extension not in permitidas:
        raise ValueError("El tipo de archivo no está permitido.")
    contenido = archivo.read(limite_bytes + 1)
    if not contenido or len(contenido) > limite_bytes:
        raise ValueError("El archivo está vacío o supera el tamaño permitido.")
    if validar_imagen or extension in {"jpg", "jpeg", "png", "webp"}:
        try:
            with Image.open(BytesIO(contenido)) as imagen:
                imagen.verify()
        except Exception as error:
            raise ValueError("El archivo no contiene una imagen válida.") from error
    elif extension == "pdf" and not contenido.startswith(b"%PDF-"):
        raise ValueError("El archivo no contiene un PDF válido.")

    raiz = raiz_local_aislada()
    segmentos_espacio = [
        _nombre_seguro(segmento)
        for segmento in str(espacio or "general").replace("\\", "/").split("/")
        if str(segmento).strip()
    ]
    espacio_seguro = "/".join(segmentos_espacio) or "general"
    directorio = (
        raiz / f"organizacion_{organizacion_id}"
        / f"unidad_{unidad_negocio_id}" / espacio_seguro
    ).resolve()
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
        "url": (
            f"/archivos-uat/{organizacion_id}/{unidad_negocio_id}/"
            f"{ruta_relativa}"
        ),
        "public_id": (
            f"local:{organizacion_id}:{unidad_negocio_id}:{ruta_relativa}"
        ),
        "principal": False,
        "nombre": nombre,
        "size_bytes": len(contenido),
    }


def guardar_imagen_local(
    archivo, *, organizacion_id, unidad_negocio_id, espacio, limite_bytes,
):
    """Valida y guarda una imagen con nombre no controlado por el usuario."""
    return guardar_archivo_local(
        archivo,
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
        espacio=espacio,
        limite_bytes=limite_bytes,
        extensiones_permitidas={"jpg", "jpeg", "png", "webp"},
        validar_imagen=True,
    )
