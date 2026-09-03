"""Diagnostico reproducible del costo interno, sin publicar ni activar precios."""

from hashlib import sha256
import json
from decimal import Decimal, InvalidOperation

from services.composicion_costo_producto import (
    construir_detalles,
    construir_detalles_combo,
)
from services.costos_productos import preparar_detalles


ESTADOS_RECALCULABLES = {"sin_calcular", "desactualizado"}


def _valor(valor):
    if valor is None:
        return ""
    try:
        return format(Decimal(str(valor)).normalize(), "f")
    except (InvalidOperation, ValueError):
        return str(valor)


def huella_detalles(detalles):
    """Representa el snapshot sin depender de ids ni fechas de base de datos."""
    normalizados = []
    for posicion, detalle in enumerate(detalles):
        obtener = detalle.get if isinstance(detalle, dict) else lambda k, d=None: getattr(detalle, k, d)
        normalizados.append({
            "tipo": obtener("tipo"),
            "codigo": obtener("codigo"),
            "concepto": obtener("concepto"),
            "cantidad": _valor(obtener("cantidad")),
            "unidad_medida": obtener("unidad_medida"),
            "costo_unitario_centavos": int(obtener("costo_unitario_centavos") or 0),
            "porcentaje_merma": _valor(obtener("porcentaje_merma", 0)),
            "subtotal_centavos": int(obtener("subtotal_centavos") or 0),
            "orden": int(obtener("orden", posicion)),
        })
    contenido = json.dumps(normalizados, ensure_ascii=False, sort_keys=True)
    return sha256(contenido.encode("utf-8")).hexdigest()


def diagnosticar_perfil(perfil, versiones, *, CostoProductoVersion):
    """Evalua una ficha sin persistir, activar ni modificar ningun registro."""
    base = {
        "perfil_id": getattr(perfil, "id", None),
        "producto_id": getattr(perfil, "producto_id", None),
        "sku": getattr(getattr(perfil, "producto", None), "sku", ""),
        "tipo": getattr(perfil, "tipo", None),
        "estado": "incompleto",
        "detalle": "",
        "costo_estimado_centavos": None,
        "ultima_version": None,
        "puede_recalcular": False,
    }
    if not getattr(perfil, "activo", True):
        base.update(estado="inactivo", detalle="El perfil de costo está inactivo.")
        return base
    propias = sorted(
        [
            version for version in versiones
            if version.producto_id == perfil.producto_id
            and version.organizacion_id == perfil.organizacion_id
            and version.unidad_negocio_id == perfil.unidad_negocio_id
            and version.moneda == "ARS"
            and version.estado != "cancelado"
        ],
        key=lambda version: version.numero_version,
    )
    ultima = propias[-1] if propias else None
    base["ultima_version"] = ultima
    if perfil.tipo == "simple":
        base.update(
            estado="manual_disponible" if ultima else "manual_pendiente",
            detalle=(
                "Tiene costo manual registrado."
                if ultima else "Requiere cargar un costo de compra manual."
            ),
        )
        return base
    try:
        detalles = (
            construir_detalles_combo(
                perfil, CostoProductoVersion=CostoProductoVersion,
            )
            if perfil.tipo == "combo" else construir_detalles(perfil)
        )
        preparados = preparar_detalles(detalles)
    except ValueError as error:
        base["detalle"] = str(error)
        return base
    total = sum(item["subtotal_centavos"] for item in preparados)
    base["costo_estimado_centavos"] = total
    if ultima is None:
        base.update(
            estado="sin_calcular", detalle="La ficha está completa y aún no tiene versión.",
            puede_recalcular=True,
        )
    elif huella_detalles(preparados) != huella_detalles(ultima.detalles):
        base.update(
            estado="desactualizado",
            detalle="La composición o una fuente vigente cambió.",
            puede_recalcular=True,
        )
    else:
        base.update(
            estado="actualizado", detalle="La última versión reproduce las fuentes vigentes.",
        )
    return base


def diagnosticar_perfiles(perfiles, versiones, *, CostoProductoVersion):
    diagnosticos = {
        perfil.id: diagnosticar_perfil(
            perfil, versiones, CostoProductoVersion=CostoProductoVersion,
        )
        for perfil in perfiles
    }
    resumen = {
        "total": len(diagnosticos), "actualizados": 0, "pendientes": 0,
        "incompletos": 0, "manuales": 0,
    }
    for item in diagnosticos.values():
        if item["estado"] == "actualizado":
            resumen["actualizados"] += 1
        elif item["estado"] in ESTADOS_RECALCULABLES:
            resumen["pendientes"] += 1
        elif item["estado"].startswith("manual_"):
            resumen["manuales"] += 1
        else:
            resumen["incompletos"] += 1
    return diagnosticos, resumen
