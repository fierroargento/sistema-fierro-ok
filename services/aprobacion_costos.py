"""Revision y decisiones humanas sobre costos internos versionados."""

from decimal import Decimal, ROUND_HALF_UP

from services.composicion_costo_producto import (
    construir_detalles,
    construir_detalles_combo,
)
from services.costos_productos import preparar_detalles
from services.fechas import ahora_utc_naive
from services.motor_costeo_productos import huella_detalles


def comparar_versiones(candidata, vigente):
    nuevo = int(candidata.costo_total_centavos)
    anterior = int(vigente.costo_total_centavos) if vigente else None
    diferencia = None if anterior is None else nuevo - anterior
    porcentaje = None
    if anterior not in {None, 0}:
        porcentaje = (
            Decimal(diferencia) * Decimal("100") / Decimal(anterior)
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "costo_anterior_centavos": anterior,
        "costo_nuevo_centavos": nuevo,
        "diferencia_centavos": diferencia,
        "diferencia_pct": porcentaje,
    }


def validar_version_preparatoria(perfil, version, *, CostoProductoVersion):
    if version is None or version.estado != "preparatorio" or version.vigente:
        raise ValueError("La versión ya no está pendiente de aprobación.")
    if (
        perfil is None
        or perfil.organizacion_id != version.organizacion_id
        or perfil.unidad_negocio_id != version.unidad_negocio_id
        or perfil.producto_id != version.producto_id
        or not perfil.activo
    ):
        raise ValueError("La versión no coincide con un perfil activo de la unidad.")
    if perfil.tipo == "simple":
        if version.tipo != "manual" or not version.detalles:
            raise ValueError("El producto simple requiere un costo manual completo.")
        return True
    actuales = (
        construir_detalles_combo(
            perfil, CostoProductoVersion=CostoProductoVersion,
        )
        if perfil.tipo == "combo" else construir_detalles(perfil)
    )
    if huella_detalles(preparar_detalles(actuales)) != huella_detalles(
        version.detalles
    ):
        raise ValueError(
            "La versión quedó desactualizada; recalculala antes de aprobar."
        )
    return True


def rechazar_version(version, motivo, *, db_session, commit=True):
    if version is None or version.estado != "preparatorio" or version.vigente:
        raise ValueError("Solo se puede rechazar una versión preparatoria.")
    razon = str(motivo or "").strip()
    if not razon:
        raise ValueError("Indicá el motivo del rechazo.")
    version.estado = "cancelado"
    version.observacion = _anotar(version.observacion, f"Rechazada: {razon}")
    if commit:
        db_session.commit()
    return version


def archivar_version(version, motivo, *, db_session, commit=True):
    if version is None or version.estado not in {"preparatorio", "vigente"}:
        raise ValueError("La versión no se puede archivar desde su estado actual.")
    razon = str(motivo or "").strip()
    if not razon:
        raise ValueError("Indicá el motivo del archivo.")
    version.estado = "archivado"
    if version.vigente:
        version.vigente = False
        version.vigente_hasta = ahora_utc_naive()
    version.observacion = _anotar(version.observacion, f"Archivada: {razon}")
    if commit:
        db_session.commit()
    return version


def _anotar(anterior, nota):
    partes = [str(anterior or "").strip(), nota]
    return " | ".join(parte for parte in partes if parte)[:500]


def preparar_revisiones(perfiles, versiones):
    revisiones = []
    por_producto = {perfil.producto_id: perfil for perfil in perfiles}
    for producto_id, perfil in por_producto.items():
        propias = [
            version for version in versiones
            if version.producto_id == producto_id and version.moneda == "ARS"
        ]
        vigentes = [v for v in propias if v.vigente]
        vigente = max(vigentes, key=lambda version: version.numero_version) if vigentes else None
        pendientes = [
            v for v in propias
            if v.estado == "preparatorio"
            and (vigente is None or v.numero_version > vigente.numero_version)
        ]
        if not pendientes:
            continue
        candidata = max(pendientes, key=lambda version: version.numero_version)
        revisiones.append({
            "perfil": perfil,
            "candidata": candidata,
            "vigente": vigente,
            **comparar_versiones(candidata, vigente),
        })
    return sorted(revisiones, key=lambda item: item["perfil"].producto.sku)
