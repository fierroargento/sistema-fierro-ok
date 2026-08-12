"""Distribución histórica de costos fijos por unidad y ubicación."""

from decimal import Decimal, InvalidOperation

from services.fechas import ahora_utc_naive


def _porcentaje(valor, nombre):
    try:
        numero = Decimal(str(valor or "0").replace(",", ".").strip())
    except (InvalidOperation, AttributeError, ValueError) as error:
        raise ValueError(f"{nombre} no es válido.") from error
    if not numero.is_finite() or numero < 0 or numero > 100:
        raise ValueError(f"{nombre} debe estar entre 0 y 100.")
    return numero


def normalizar_distribucion_costo_fijo(filas):
    resultado = []
    unidades = set()
    for fila in filas:
        asignacion = _porcentaje(fila.get("porcentaje_asignacion"), "La asignación")
        if asignacion == 0:
            continue
        unidad_id = int(fila.get("unidad_negocio_id") or 0)
        if unidad_id <= 0 or unidad_id in unidades:
            raise ValueError("Las unidades de la distribución no son válidas.")
        ubicacion = str(fila.get("ubicacion_costo") or "").strip()
        if not ubicacion:
            raise ValueError("Cada asignación debe indicar Taller, Salón u otra ubicación.")
        productivo = _porcentaje(
            fila.get("porcentaje_productivo"), "El porcentaje productivo",
        )
        unidades.add(unidad_id)
        resultado.append({
            "unidad_negocio_id": unidad_id,
            "ubicacion_costo": ubicacion,
            "porcentaje_asignacion": asignacion,
            "porcentaje_productivo": productivo,
        })
    total = sum((fila["porcentaje_asignacion"] for fila in resultado), Decimal("0"))
    if total != Decimal("100"):
        raise ValueError(f"La distribución debe sumar 100% y actualmente suma {total}%.")
    return resultado


def registrar_distribucion_costo_fijo(
    costo, filas, *, organizacion_id, unidades_validas, Modelo,
    db_session, usuario_id=None, observacion=None,
):
    asignaciones = normalizar_distribucion_costo_fijo(filas)
    permitidas = {int(unidad.id) for unidad in unidades_validas}
    if any(fila["unidad_negocio_id"] not in permitidas for fila in asignaciones):
        raise ValueError("Una unidad no pertenece a la organización.")
    if int(costo.organizacion_id) != int(organizacion_id):
        raise ValueError("El costo fijo no pertenece a la organización.")
    ahora = ahora_utc_naive()
    vigentes = Modelo.query.filter_by(costo_fijo_id=costo.id, vigente=True).all()
    revision = max(
        (fila.numero_revision for fila in costo.distribuciones_versionadas),
        default=0,
    ) + 1
    for anterior in vigentes:
        anterior.vigente = False
        anterior.vigente_hasta = ahora
    creadas = []
    for fila in asignaciones:
        nueva = Modelo(
            organizacion_id=organizacion_id,
            costo_fijo_id=costo.id,
            numero_revision=revision,
            vigente=True,
            vigente_desde=ahora,
            observacion=str(observacion or "").strip() or None,
            creado_por_usuario_id=usuario_id,
            **fila,
        )
        db_session.add(nueva)
        creadas.append(nueva)
    costo.integra_costo_produccion = any(
        fila["porcentaje_productivo"] > 0 for fila in asignaciones
    )
    if not costo.integra_costo_produccion:
        costo.criterio_distribucion = "sin_distribuir"
    elif costo.criterio_distribucion == "sin_distribuir":
        costo.criterio_distribucion = "porcentaje"
    db_session.commit()
    return revision, creadas


def distribuciones_costos_fijos_vigentes(costos, *, Modelo):
    resultado = {costo.id: {} for costo in costos}
    ids = list(resultado)
    if not ids:
        return resultado
    for fila in Modelo.query.filter(
        Modelo.costo_fijo_id.in_(ids), Modelo.vigente.is_(True),
    ).all():
        resultado.setdefault(fila.costo_fijo_id, {})[fila.unidad_negocio_id] = fila
    return resultado
