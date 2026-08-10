"""Configuracion y calculo de fichas de costo, sin costos comerciales."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def _positivo(valor, campo, maximo=None):
    try:
        numero = Decimal(str(valor).replace(",", ".").strip())
    except (InvalidOperation, AttributeError, ValueError) as error:
        raise ValueError(f"{campo} no es valido.") from error
    if not numero.is_finite() or numero <= 0 or (maximo is not None and numero > maximo):
        raise ValueError(f"{campo} esta fuera de rango.")
    return numero


def _alcance(perfil, recurso):
    if perfil is None or perfil.tipo != "produccion":
        raise ValueError("La ficha técnica requiere un producto de producción.")
    if recurso is None or int(recurso.organizacion_id) != int(perfil.organizacion_id):
        raise ValueError("El recurso no pertenece a la organización.")
    if recurso.unidad_negocio_id not in {None, perfil.unidad_negocio_id}:
        raise ValueError("El recurso no pertenece a la unidad del producto.")


def guardar_insumo(perfil, insumo, *, cantidad, merma, observacion, Modelo, db_session):
    _alcance(perfil, insumo)
    registro = Modelo.query.filter_by(perfil_costeo_id=perfil.id, insumo_id=insumo.id).first()
    if registro is None:
        registro = Modelo(perfil_costeo_id=perfil.id, insumo_id=insumo.id)
        db_session.add(registro)
    registro.cantidad = _positivo(cantidad, "La cantidad")
    registro.porcentaje_merma = Decimal("0") if str(merma or "").strip() in {"", "0"} else _positivo(merma, "La merma", Decimal("100"))
    registro.observacion = str(observacion or "").strip() or None
    db_session.commit()
    return registro


def guardar_operacion(perfil, empleado, *, nombre, minutos, observacion, Modelo, db_session, registro_id=None):
    _alcance(perfil, empleado)
    descripcion = str(nombre or "").strip()
    if not descripcion:
        raise ValueError("La operación requiere un nombre.")
    registro = None
    if registro_id is not None:
        registro = Modelo.query.filter_by(id=int(registro_id), perfil_costeo_id=perfil.id).first()
        if registro is None:
            raise ValueError("La operación no pertenece a la ficha activa.")
    if registro is None:
        registro = Modelo(perfil_costeo_id=perfil.id, orden=len(perfil.operaciones_costeo))
        db_session.add(registro)
    registro.empleado_id = empleado.id
    registro.nombre = descripcion[:160]
    registro.minutos = _positivo(minutos, "Los minutos")
    registro.observacion = str(observacion or "").strip() or None
    db_session.commit()
    return registro


def guardar_costo_fijo(perfil, costo_fijo, *, porcentaje, unidades_mensuales, observacion, Modelo, db_session):
    _alcance(perfil, costo_fijo)
    if not costo_fijo.integra_costo_produccion:
        raise ValueError("El costo fijo no está marcado como productivo.")
    registro = Modelo.query.filter_by(perfil_costeo_id=perfil.id, costo_fijo_id=costo_fijo.id).first()
    if registro is None:
        registro = Modelo(perfil_costeo_id=perfil.id, costo_fijo_id=costo_fijo.id)
        db_session.add(registro)
    registro.porcentaje_asignacion = _positivo(porcentaje, "El porcentaje", Decimal("100"))
    registro.unidades_mensuales = _positivo(unidades_mensuales, "Las unidades mensuales")
    registro.observacion = str(observacion or "").strip() or None
    db_session.commit(); return registro


def eliminar_linea(modelo, registro_id, perfil, *, db_session):
    registro = modelo.query.filter_by(id=registro_id, perfil_costeo_id=perfil.id).first()
    if registro is None:
        raise ValueError("La línea no pertenece a la ficha activa.")
    db_session.delete(registro); db_session.commit()


def _vigente(versiones):
    return next((item for item in versiones if item.vigente and item.moneda == "ARS"), None)


def construir_detalles(perfil):
    if perfil.tipo != "produccion":
        raise ValueError("Solo los productos de producción usan ficha técnica.")
    detalles, orden = [], 0
    for linea in perfil.insumos_costeo:
        version = _vigente(linea.insumo.versiones_precio)
        if version is None:
            raise ValueError(f"{linea.insumo.nombre} no tiene precio vigente.")
        detalles.append({
            "tipo": "insumo", "codigo": linea.insumo.codigo,
            "concepto": linea.insumo.nombre, "cantidad": linea.cantidad,
            "unidad_medida": linea.insumo.unidad_medida,
            "costo_unitario_centavos": version.precio_unitario_centavos,
            "porcentaje_merma": linea.porcentaje_merma, "orden": orden,
            "observacion": linea.observacion,
        }); orden += 1
    for linea in sorted(perfil.operaciones_costeo, key=lambda item: item.orden):
        version = _vigente(linea.empleado.versiones_costo)
        if version is None:
            raise ValueError(f"{linea.empleado.nombre} no tiene costo vigente.")
        detalles.append({
            "tipo": "mano_obra", "codigo": linea.empleado.codigo,
            "concepto": linea.nombre, "cantidad": linea.minutos,
            "unidad_medida": "minuto", "costo_unitario_centavos": version.costo_minuto_productivo_centavos,
            "porcentaje_merma": 0, "orden": orden, "observacion": linea.observacion,
        }); orden += 1
    for linea in perfil.costos_fijos_costeo:
        version = _vigente(linea.costo_fijo.versiones)
        if version is None:
            raise ValueError(f"{linea.costo_fijo.nombre} no tiene importe vigente.")
        unitario = (
            Decimal(version.importe_mensual_centavos)
            * linea.porcentaje_asignacion / Decimal("100")
            / linea.unidades_mensuales
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        detalles.append({
            "tipo": "elaboracion", "codigo": linea.costo_fijo.codigo,
            "concepto": linea.costo_fijo.nombre, "cantidad": 1,
            "unidad_medida": "unidad", "costo_unitario_centavos": int(unitario),
            "porcentaje_merma": 0, "orden": orden, "observacion": linea.observacion,
        }); orden += 1
    if not detalles:
        raise ValueError("La ficha técnica todavía no tiene componentes.")
    return detalles


def construir_detalles_combo(perfil, *, CostoProductoVersion):
    if perfil.tipo != "combo":
        raise ValueError("El producto seleccionado no es un combo.")
    detalles = []
    for orden, linea in enumerate(perfil.componentes_combo):
        costo = CostoProductoVersion.query.filter_by(
            organizacion_id=perfil.organizacion_id,
            unidad_negocio_id=perfil.unidad_negocio_id,
            producto_id=linea.componente.producto_id,
            moneda="ARS", vigente=True,
        ).first()
        if costo is None:
            raise ValueError(
                f"{linea.componente.producto.sku} no tiene costo vigente."
            )
        detalles.append({
            "tipo": "elaboracion", "codigo": linea.componente.producto.sku,
            "concepto": linea.componente.producto.descripcion,
            "cantidad": linea.cantidad, "unidad_medida": "unidad",
            "costo_unitario_centavos": costo.costo_total_centavos,
            "porcentaje_merma": 0, "orden": orden,
            "observacion": linea.observacion,
        })
    if not detalles:
        raise ValueError("El combo todavía no tiene componentes.")
    return detalles
