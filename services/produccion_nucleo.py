"""Planificación tenant de producción, deliberadamente no ejecutable."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def _cantidad(valor):
    try:
        numero = Decimal(str(valor or "").replace(",", "."))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("La cantidad planificada no es válida.") from error
    if not numero.is_finite() or numero <= 0:
        raise ValueError("La cantidad planificada debe ser mayor que cero.")
    return numero.quantize(Decimal("0.000001"))


def crear_orden_preparatoria(datos, *, perfil, version_costo, organizacion_id,
                              unidad_negocio_id, modelos, db_session, usuario_id=None):
    if int(perfil.organizacion_id) != int(organizacion_id):
        raise ValueError("El perfil no pertenece al tenant activo.")
    if perfil.unidad_negocio_id not in {None, unidad_negocio_id}:
        raise ValueError("El perfil no pertenece a la unidad activa.")
    if perfil.tipo != "produccion" or not perfil.activo:
        raise ValueError("Solo un perfil productivo activo admite planificación.")
    if version_costo is None or not version_costo.vigente:
        raise ValueError("El producto necesita una versión de costo vigente.")
    if int(version_costo.organizacion_id) != int(organizacion_id):
        raise ValueError("La versión de costo no pertenece al tenant activo.")
    if version_costo.unidad_negocio_id not in {None, unidad_negocio_id}:
        raise ValueError("La versión de costo no pertenece a la unidad activa.")
    if int(version_costo.producto_id) != int(perfil.producto_id):
        raise ValueError("La versión de costo no corresponde al producto del perfil.")
    cantidad = _cantidad(datos.get("cantidad"))
    costo_unitario = int(version_costo.costo_total_centavos)
    total = int((cantidad * Decimal(costo_unitario)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    orden = modelos["OrdenProduccion"](
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
        perfil_costeo_id=perfil.id, producto_id=perfil.producto_id,
        numero=str(datos.get("numero") or "").strip().upper(),
        cantidad_planificada=cantidad, estado="borrador",
        costo_unitario_centavos=costo_unitario, costo_planificado_centavos=total,
        version_costo_id=version_costo.id, impacta_inventario=False,
        ejecucion_habilitada=False,
        observacion=str(datos.get("observacion") or "").strip() or None,
        creado_por_usuario_id=usuario_id,
    )
    if not orden.numero:
        raise ValueError("El número de orden es obligatorio.")
    for ficha in perfil.insumos_costeo:
        _validar_recurso_ficha(
            ficha.insumo, organizacion_id, unidad_negocio_id, "insumo",
        )
        factor_merma = Decimal("1") + Decimal(str(ficha.porcentaje_merma)) / Decimal("100")
        orden.insumos_planificados.append(modelos["OrdenProduccionInsumo"](
            insumo_id=ficha.insumo_id,
            cantidad_planificada=(Decimal(str(ficha.cantidad)) * cantidad * factor_merma).quantize(Decimal("0.000001")),
            porcentaje_merma=ficha.porcentaje_merma, consumo_registrado=False,
        ))
    for ficha in perfil.operaciones_costeo:
        _validar_recurso_ficha(
            ficha.empleado, organizacion_id, unidad_negocio_id, "empleado",
        )
        orden.operaciones_planificadas.append(modelos["OrdenProduccionOperacion"](
            empleado_id=ficha.empleado_id, nombre=ficha.nombre,
            minutos_planificados=Decimal(str(ficha.minutos)) * cantidad,
            avance_registrado=False,
        ))
    for ficha in perfil.maquinas_costeo:
        _validar_recurso_ficha(
            ficha.maquina, organizacion_id, unidad_negocio_id, "máquina",
        )
        orden.maquinas_planificadas.append(modelos["OrdenProduccionMaquina"](
            maquina_id=ficha.maquina_id, nombre=ficha.nombre,
            minutos_planificados=Decimal(str(ficha.minutos)) * cantidad,
            uso_registrado=False,
        ))
    if not orden.insumos_planificados or not orden.operaciones_planificadas:
        raise ValueError("La ficha productiva necesita insumos y operaciones.")
    db_session.add(orden)
    db_session.commit()
    return orden


def _validar_recurso_ficha(recurso, organizacion_id, unidad_negocio_id, nombre):
    if int(getattr(recurso, "organizacion_id", 0) or 0) != int(organizacion_id):
        raise ValueError(f"El {nombre} de la ficha no pertenece al tenant activo.")
    unidad = getattr(recurso, "unidad_negocio_id", None)
    if unidad not in {None, unidad_negocio_id}:
        raise ValueError(f"El {nombre} de la ficha no pertenece a la unidad activa.")
    if not bool(getattr(recurso, "activo", False)):
        raise ValueError(f"El {nombre} de la ficha está desactivado.")


def cambiar_estado(orden, estado, *, organizacion_id, unidad_negocio_id, db_session):
    if int(orden.organizacion_id) != int(organizacion_id) or int(orden.unidad_negocio_id) != int(unidad_negocio_id):
        raise ValueError("La orden no pertenece al tenant y unidad activos.")
    permitidas = {
        "borrador": {"en_revision", "cancelada"},
        "en_revision": {"aprobada", "borrador", "cancelada"},
        "aprobada": {"cerrada", "cancelada"},
        "cerrada": set(), "cancelada": set(),
    }
    if estado not in permitidas.get(orden.estado, set()):
        raise ValueError("La transición productiva no está permitida.")
    orden.estado = estado
    orden.impacta_inventario = False
    orden.ejecucion_habilitada = False
    db_session.commit()
    return orden
