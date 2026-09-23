"""Persistencia segura de documentos asociados a pedidos."""

from services.almacenamiento_archivos import (
    almacenamiento_local_habilitado,
    guardar_archivo_local,
)
from services.seguridad_entorno import exigir_conexion_externa, exigir_efecto_externo


_TIPOS = {
    "etiqueta": {
        "extensiones": {"pdf", "jpg", "jpeg", "png", "webp"},
        "limite": 10 * 1024 * 1024,
        "resource_type": "auto",
    },
    "comprobante_dux": {
        "extensiones": {"pdf"},
        "limite": 15 * 1024 * 1024,
        "resource_type": "auto",
    },
    "comprobante_pago": {
        "extensiones": {"pdf", "jpg", "jpeg", "png", "webp"},
        "limite": 15 * 1024 * 1024,
        "resource_type": "auto",
    },
}


def _identidad(organizacion_id, unidad_negocio_id):
    try:
        organizacion_id = int(organizacion_id)
        unidad_negocio_id = int(unidad_negocio_id)
    except (TypeError, ValueError) as error:
        raise ValueError("El documento requiere organización y unidad válidas.") from error
    if organizacion_id <= 0 or unidad_negocio_id <= 0:
        raise ValueError("El documento requiere organización y unidad válidas.")
    return organizacion_id, unidad_negocio_id


def guardar_documento_pedido(
    archivo, *, tipo, organizacion_id, unidad_negocio_id, pedido_id,
    cloudinary_uploader=None, logger_fn=print,
):
    """Guarda localmente en UAT o usa Cloudinary bajo doble habilitación."""
    if not archivo or not getattr(archivo, "filename", ""):
        return {"url": "", "public_id": ""}
    if tipo not in _TIPOS:
        raise ValueError("Tipo de documento de pedido no permitido.")
    organizacion_id, unidad_negocio_id = _identidad(
        organizacion_id, unidad_negocio_id,
    )
    pedido_ref = str(pedido_id or "nuevo").strip() or "nuevo"
    config = _TIPOS[tipo]
    espacio = f"pedidos/{pedido_ref}/{tipo}"

    if almacenamiento_local_habilitado():
        return guardar_archivo_local(
            archivo,
            organizacion_id=organizacion_id,
            unidad_negocio_id=unidad_negocio_id,
            espacio=espacio,
            limite_bytes=config["limite"],
            extensiones_permitidas=config["extensiones"],
        )

    exigir_conexion_externa("CLOUDINARY", f"Carga de {tipo} de pedido")
    exigir_efecto_externo("CLOUDINARY", f"Carga de {tipo} de pedido")
    if cloudinary_uploader is None:
        raise RuntimeError("No hay cargador Cloudinary configurado.")
    try:
        resultado = cloudinary_uploader.upload(
            archivo,
            folder=(
                f"sistema_fierro/{organizacion_id}/{unidad_negocio_id}/"
                f"pedidos/{pedido_ref}/{tipo}"
            ),
            resource_type=config["resource_type"],
            use_filename=True,
            unique_filename=True,
            overwrite=False,
            context={
                "organizacion_id": str(organizacion_id),
                "unidad_negocio_id": str(unidad_negocio_id),
                "pedido_id": pedido_ref,
                "tipo": tipo,
            },
        )
    except Exception as error:
        if logger_fn is not None:
            logger_fn(f"Error guardando {tipo} en Cloudinary: {error}")
        return {"url": "", "public_id": ""}
    return {
        "url": resultado.get("secure_url", ""),
        "public_id": resultado.get("public_id", ""),
    }


def referencia_local_pertenece_tenant(
    referencia, *, organizacion_id, unidad_negocio_id,
):
    """Valida referencias UAT sin aceptar prefijos de otro tenant."""
    referencia = str(referencia or "").strip()
    if not referencia:
        return True
    if not almacenamiento_local_habilitado():
        return True
    organizacion_id, unidad_negocio_id = _identidad(
        organizacion_id, unidad_negocio_id,
    )
    prefijo = f"/archivos-uat/{organizacion_id}/{unidad_negocio_id}/"
    return referencia.startswith(prefijo) and ".." not in referencia
