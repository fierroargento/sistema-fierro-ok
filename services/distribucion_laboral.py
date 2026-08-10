"""Distribución histórica y multiunidad del costo de empleados."""

from decimal import Decimal, InvalidOperation

from services.fechas import ahora_utc_naive


TIPOS_FUNCION = {
    "directa", "indirecta_productiva", "comercial_administrativa", "mixta",
}


def _porcentaje(valor):
    try:
        numero = Decimal(str(valor or "0").replace(",", ".").strip())
    except (InvalidOperation, AttributeError, ValueError) as error:
        raise ValueError("El porcentaje de distribución no es válido.") from error
    if not numero.is_finite() or numero < 0 or numero > 100:
        raise ValueError("Cada porcentaje debe estar entre 0 y 100.")
    return numero


def normalizar_asignaciones(filas):
    """Descarta filas en cero y exige una distribución completa, sin duplicados."""
    asignaciones = []
    unidades = set()
    for fila in filas:
        porcentaje = _porcentaje(fila.get("porcentaje_asignacion"))
        if porcentaje == 0:
            continue
        unidad_id = int(fila.get("unidad_negocio_id") or 0)
        if unidad_id <= 0:
            raise ValueError("La unidad de negocio no es válida.")
        if unidad_id in unidades:
            raise ValueError("No se puede repetir una unidad de negocio.")
        ubicacion = str(fila.get("ubicacion_trabajo") or "").strip()
        if not ubicacion:
            raise ValueError("Toda asignación debe indicar una ubicación.")
        tipo = str(fila.get("tipo_funcion") or "").strip().lower()
        if tipo not in TIPOS_FUNCION:
            raise ValueError("La función de costo no es válida.")
        unidades.add(unidad_id)
        asignaciones.append({
            "unidad_negocio_id": unidad_id,
            "ubicacion_trabajo": ubicacion,
            "tipo_funcion": tipo,
            "porcentaje_asignacion": porcentaje,
        })
    total = sum((fila["porcentaje_asignacion"] for fila in asignaciones), Decimal("0"))
    if total != Decimal("100"):
        raise ValueError(f"La distribución debe sumar 100% y actualmente suma {total}%.")
    return asignaciones


def registrar_distribucion(
    empleado, filas, *, organizacion_id, unidades_validas, Modelo,
    db_session, usuario_id=None, observacion=None,
):
    asignaciones = normalizar_asignaciones(filas)
    permitidas = {int(unidad.id) for unidad in unidades_validas}
    if any(fila["unidad_negocio_id"] not in permitidas for fila in asignaciones):
        raise ValueError("Una unidad no pertenece a la organización.")
    if int(empleado.organizacion_id) != int(organizacion_id):
        raise ValueError("El empleado no pertenece a la organización.")
    vigentes = Modelo.query.filter_by(empleado_id=empleado.id, vigente=True).all()
    ahora = ahora_utc_naive()
    revision = max(
        (fila.numero_revision for fila in empleado.distribuciones_versionadas),
        default=0,
    ) + 1
    for anterior in vigentes:
        anterior.vigente = False
        anterior.vigente_hasta = ahora
    creadas = []
    for fila in asignaciones:
        nueva = Modelo(
            organizacion_id=organizacion_id,
            empleado_id=empleado.id,
            numero_revision=revision,
            vigente=True,
            vigente_desde=ahora,
            observacion=str(observacion or "").strip() or None,
            creado_por_usuario_id=usuario_id,
            **fila,
        )
        db_session.add(nueva)
        creadas.append(nueva)
    db_session.commit()
    return revision, creadas


def distribuciones_vigentes(empleados, *, Modelo):
    ids = [empleado.id for empleado in empleados]
    resultado = {empleado.id: {} for empleado in empleados}
    if not ids:
        return resultado
    for fila in Modelo.query.filter(
        Modelo.empleado_id.in_(ids), Modelo.vigente.is_(True),
    ).all():
        resultado.setdefault(fila.empleado_id, {})[fila.unidad_negocio_id] = fila
    return resultado
