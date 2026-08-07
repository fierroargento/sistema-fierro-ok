"""Reglas tenant para tipos de producto y composicion de combos."""

from decimal import Decimal, InvalidOperation


TIPOS_PERFIL_COSTEO = {"simple", "produccion", "combo"}


def _cantidad_positiva(valor):
    try:
        cantidad = Decimal(str(valor).strip())
    except (InvalidOperation, AttributeError, TypeError, ValueError) as error:
        raise ValueError("La cantidad no es valida.") from error
    if not cantidad.is_finite() or cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")
    return cantidad


def crear_o_actualizar_perfil(
    *, organizacion_id, unidad_negocio_id, producto_id, tipo,
    observacion=None, PerfilCosteoProducto, UnidadNegocio, Producto,
    db_session, commit=True,
):
    tipo_normalizado = str(tipo or "").strip().lower()
    if tipo_normalizado not in TIPOS_PERFIL_COSTEO:
        raise ValueError("El tipo de producto no es valido.")
    producto = db_session.get(Producto, producto_id)
    if producto is None:
        raise ValueError("El producto no existe.")
    if unidad_negocio_id is not None:
        unidad = db_session.get(UnidadNegocio, unidad_negocio_id)
        if unidad is None or int(unidad.organizacion_id) != int(organizacion_id):
            raise ValueError("La unidad no pertenece a la organizacion.")

    consulta = PerfilCosteoProducto.query.filter_by(
        organizacion_id=organizacion_id,
        producto_id=producto_id,
    )
    consulta = consulta.filter(
        PerfilCosteoProducto.unidad_negocio_id.is_(None)
        if unidad_negocio_id is None
        else PerfilCosteoProducto.unidad_negocio_id == unidad_negocio_id
    )
    perfil = consulta.first()
    if perfil is None:
        perfil = PerfilCosteoProducto(
            organizacion_id=organizacion_id,
            unidad_negocio_id=unidad_negocio_id,
            producto_id=producto_id,
        )
        db_session.add(perfil)
    if perfil.tipo == "combo" and tipo_normalizado != "combo" and perfil.componentes_combo:
        raise ValueError("Eliminá los componentes antes de cambiar el tipo del combo.")
    perfil.tipo = tipo_normalizado
    perfil.observacion = str(observacion or "").strip() or None
    try:
        if commit:
            db_session.commit()
        else:
            db_session.flush()
    except Exception:
        db_session.rollback()
        raise
    return perfil


def agregar_componente_combo(
    combo, componente, *, cantidad, observacion=None,
    ComboProductoComponente, db_session,
):
    if combo is None or combo.tipo != "combo":
        raise ValueError("El producto principal no es un combo.")
    if componente is None or componente.tipo == "combo":
        raise ValueError("Un combo solo puede contener productos simples o de produccion.")
    if combo.id == componente.id:
        raise ValueError("Un combo no puede contenerse a si mismo.")
    if int(combo.organizacion_id) != int(componente.organizacion_id):
        raise ValueError("Los productos pertenecen a organizaciones diferentes.")
    if combo.unidad_negocio_id != componente.unidad_negocio_id:
        raise ValueError("El componente debe pertenecer a la misma unidad del combo.")
    existente = ComboProductoComponente.query.filter_by(
        combo_perfil_id=combo.id,
        componente_perfil_id=componente.id,
    ).first()
    if existente is not None:
        raise ValueError("El producto ya forma parte del combo.")
    registro = ComboProductoComponente(
        combo_perfil_id=combo.id,
        componente_perfil_id=componente.id,
        cantidad=_cantidad_positiva(cantidad),
        observacion=str(observacion or "").strip() or None,
    )
    try:
        db_session.add(registro)
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    return registro


def crear_o_actualizar_componente_combo(
    combo, componente, *, cantidad, observacion=None,
    ComboProductoComponente, db_session, commit=True,
):
    if combo is None or combo.tipo != "combo":
        raise ValueError("El producto principal no es un combo.")
    if componente is None or componente.tipo == "combo":
        raise ValueError("El componente debe ser simple o de produccion.")
    if combo.id == componente.id:
        raise ValueError("Un combo no puede contenerse a si mismo.")
    if (
        int(combo.organizacion_id) != int(componente.organizacion_id)
        or combo.unidad_negocio_id != componente.unidad_negocio_id
    ):
        raise ValueError("El componente debe pertenecer al mismo tenant y unidad.")
    registro = ComboProductoComponente.query.filter_by(
        combo_perfil_id=combo.id,
        componente_perfil_id=componente.id,
    ).first()
    creado = registro is None
    if creado:
        registro = ComboProductoComponente(
            combo_perfil_id=combo.id,
            componente_perfil_id=componente.id,
        )
        db_session.add(registro)
    registro.cantidad = _cantidad_positiva(cantidad)
    registro.observacion = str(observacion or "").strip() or None
    try:
        if commit:
            db_session.commit()
        else:
            db_session.flush()
    except Exception:
        db_session.rollback()
        raise
    return registro, creado


def filas_exportables_perfiles(perfiles):
    """Contrato comun para futuras salidas Excel y PDF."""
    filas = []
    for perfil in perfiles:
        filas.append({
            "unidad": perfil.unidad_negocio.nombre if perfil.unidad_negocio else "Compartido",
            "sku": perfil.producto.sku,
            "producto": perfil.producto.descripcion,
            "tipo": perfil.tipo,
            "activo": "Si" if perfil.activo else "No",
            "observacion": perfil.observacion or "",
        })
    return filas


def filas_exportables_combos(perfiles_combo):
    filas = []
    for combo in perfiles_combo:
        for item in combo.componentes_combo:
            filas.append({
                "sku_combo": combo.producto.sku,
                "sku_componente": item.componente.producto.sku,
                "cantidad": item.cantidad,
                "tipo_componente": item.componente.tipo,
                "observacion": item.observacion or "",
            })
    return filas
