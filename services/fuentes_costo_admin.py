"""Acciones administrativas para las fuentes del costo productivo."""

from services.catalogos_comerciales import importe_a_centavos
from services.fuentes_costo_productivo import (
    crear_costo_fijo,
    crear_empleado,
    crear_insumo,
    registrar_costo_empleado,
    registrar_importe_costo_fijo,
    registrar_precio_insumo,
)
from services.perfiles_costeo import (
    agregar_componente_combo,
    crear_o_actualizar_perfil,
)
from services.composicion_costo_producto import (
    construir_detalles, construir_detalles_combo, eliminar_linea,
    guardar_costo_fijo as guardar_fijo_ficha,
    guardar_insumo as guardar_insumo_ficha, guardar_operacion,
)
from services.costos_productos import crear_version_costo


def _id(formulario, campo, opcional=False):
    valor = str(formulario.get(campo) or "").strip()
    if opcional and not valor:
        return None
    if not valor.isdigit():
        raise ValueError(f"{campo} no es valido.")
    return int(valor)


def _registro_tenant(Modelo, registro_id, organizacion_id, nombre, unidad_id=None):
    registro = Modelo.query.filter_by(
        id=registro_id,
        organizacion_id=organizacion_id,
    ).first()
    if registro is None:
        raise ValueError(f"{nombre} no pertenece a la organizacion.")
    if unidad_id is not None and registro.unidad_negocio_id not in {None, unidad_id}:
        raise ValueError(f"{nombre} no pertenece a la unidad activa.")
    return registro


def _comunes(organizacion, modelos, db_session):
    return {
        "organizacion_id": organizacion.id,
        "unidad_negocio_id": None,
        "Organizacion": modelos["Organizacion"],
        "UnidadNegocio": modelos["UnidadNegocio"],
        "db_session": db_session,
    }


def procesar_accion_fuente_costo(
    accion, formulario, *, organizacion, unidad_activa, modelos, db_session, usuario,
):
    usuario_id = getattr(usuario, "id", None)
    comunes = _comunes(organizacion, modelos, db_session)
    unidad_solicitada = _id(formulario, "unidad_negocio_id", opcional=True)
    if unidad_solicitada not in {None, unidad_activa.id}:
        raise ValueError("La fuente no pertenece a la unidad activa.")
    comunes["unidad_negocio_id"] = unidad_solicitada

    if accion == "configurar_perfil_costeo":
        inclusion = modelos["CatalogoProducto"].query.get(
            _id(formulario, "catalogo_producto_id")
        )
        if (
            inclusion is None
            or inclusion.catalogo.organizacion_id != organizacion.id
            or inclusion.catalogo.unidad_negocio_id != unidad_activa.id
        ):
            raise ValueError("El producto no pertenece a la organizacion.")
        perfil = crear_o_actualizar_perfil(
            organizacion_id=organizacion.id,
            unidad_negocio_id=inclusion.catalogo.unidad_negocio_id,
            producto_id=inclusion.producto_id,
            tipo=formulario.get("tipo"),
            observacion=formulario.get("observacion"),
            PerfilCosteoProducto=modelos["PerfilCosteoProducto"],
            UnidadNegocio=modelos["UnidadNegocio"],
            Producto=modelos["Producto"],
            db_session=db_session,
        )
        return f"{perfil.producto.sku} clasificado como {perfil.tipo}."

    if accion == "agregar_componente_combo":
        combo = _registro_tenant(
            modelos["PerfilCosteoProducto"],
            _id(formulario, "combo_perfil_id"),
            organizacion.id,
            "El combo",
        )
        componente = _registro_tenant(
            modelos["PerfilCosteoProducto"],
            _id(formulario, "componente_perfil_id"),
            organizacion.id,
            "El componente",
        )
        if combo.unidad_negocio_id != unidad_activa.id or componente.unidad_negocio_id != unidad_activa.id:
            raise ValueError("El combo y su componente deben pertenecer a la unidad activa.")
        item = agregar_componente_combo(
            combo,
            componente,
            cantidad=formulario.get("cantidad"),
            observacion=formulario.get("observacion"),
            ComboProductoComponente=modelos["ComboProductoComponente"],
            db_session=db_session,
        )
        return (
            f"{item.componente.producto.sku} incorporado al combo "
            f"{item.combo.producto.sku}."
        )

    if accion in {"ficha_insumo", "ficha_operacion", "ficha_costo_fijo", "calcular_ficha", "calcular_combo", "eliminar_linea_ficha"}:
        perfil = _registro_tenant(
            modelos["PerfilCosteoProducto"], _id(formulario, "perfil_costeo_id"),
            organizacion.id, "El producto",
        )
        if perfil.unidad_negocio_id != unidad_activa.id:
            raise ValueError("El producto no pertenece a la unidad activa.")
        if accion == "ficha_insumo":
            recurso = _registro_tenant(modelos["InsumoProductivo"], _id(formulario, "insumo_id"), organizacion.id, "El insumo", unidad_activa.id)
            guardar_insumo_ficha(perfil, recurso, cantidad=formulario.get("cantidad"), merma=formulario.get("merma", 0), observacion=formulario.get("observacion"), Modelo=modelos["ProductoInsumoCosteo"], db_session=db_session)
            return "Insumo incorporado a la ficha técnica."
        if accion == "ficha_operacion":
            recurso = _registro_tenant(modelos["EmpleadoProductivo"], _id(formulario, "empleado_id"), organizacion.id, "El empleado", unidad_activa.id)
            guardar_operacion(perfil, recurso, nombre=formulario.get("nombre_operacion"), minutos=formulario.get("minutos"), observacion=formulario.get("observacion"), Modelo=modelos["ProductoOperacionCosteo"], db_session=db_session)
            return "Operación incorporada a la ficha técnica."
        if accion == "ficha_costo_fijo":
            recurso = _registro_tenant(modelos["CostoFijoProductivo"], _id(formulario, "costo_fijo_id"), organizacion.id, "El costo fijo", unidad_activa.id)
            guardar_fijo_ficha(perfil, recurso, porcentaje=formulario.get("porcentaje"), unidades_mensuales=formulario.get("unidades_mensuales"), observacion=formulario.get("observacion"), Modelo=modelos["ProductoCostoFijoCosteo"], db_session=db_session)
            return "Costo fijo incorporado a la ficha técnica."
        if accion == "eliminar_linea_ficha":
            tipos = {"insumo": modelos["ProductoInsumoCosteo"], "operacion": modelos["ProductoOperacionCosteo"], "fijo": modelos["ProductoCostoFijoCosteo"]}
            modelo = tipos.get(str(formulario.get("tipo_linea") or ""))
            if modelo is None:
                raise ValueError("El tipo de línea no es válido.")
            eliminar_linea(modelo, _id(formulario, "linea_id"), perfil, db_session=db_session)
            return "Línea eliminada de la ficha técnica."
        detalles = (
            construir_detalles_combo(
                perfil, CostoProductoVersion=modelos["CostoProductoVersion"],
            )
            if accion == "calcular_combo" else construir_detalles(perfil)
        )
        version = crear_version_costo(
            organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id,
            producto_id=perfil.producto_id, moneda="ARS", tipo="calculado",
            detalles=detalles, creado_por_usuario_id=usuario_id,
            creado_por_username=getattr(usuario, "username", None),
            observacion=formulario.get("observacion"),
            Organizacion=modelos["Organizacion"], UnidadNegocio=modelos["UnidadNegocio"],
            Producto=modelos["Producto"], CostoProductoVersion=modelos["CostoProductoVersion"],
            CostoProductoDetalle=modelos["CostoProductoDetalle"], db_session=db_session,
        )
        return f"Costo calculado v{version.numero_version}: ${version.costo_total_centavos / 100:.2f}."

    if accion == "crear_insumo":
        insumo = crear_insumo(
            **comunes,
            codigo=formulario.get("codigo"),
            nombre=formulario.get("nombre"),
            tipo=formulario.get("tipo"),
            unidad_medida=formulario.get("unidad_medida"),
            observacion=formulario.get("observacion"),
            InsumoProductivo=modelos["InsumoProductivo"],
            commit=False,
        )
        registrar_precio_insumo(
            insumo,
            moneda=formulario.get("moneda", "ARS"),
            precio_unitario_centavos=importe_a_centavos(
                formulario.get("precio_unitario")
            ),
            proveedor_referencia=formulario.get("proveedor_referencia"),
            comprobante_referencia=formulario.get("comprobante_referencia"),
            creado_por_usuario_id=usuario_id,
            InsumoPrecioVersion=modelos["InsumoPrecioVersion"],
            db_session=db_session,
        )
        return f"Insumo {insumo.nombre} creado con su precio inicial."

    if accion == "actualizar_precio_insumo":
        insumo = _registro_tenant(
            modelos["InsumoProductivo"],
            _id(formulario, "insumo_id"),
            organizacion.id,
            "El insumo",
            unidad_activa.id,
        )
        version = registrar_precio_insumo(
            insumo,
            moneda=formulario.get("moneda", "ARS"),
            precio_unitario_centavos=importe_a_centavos(
                formulario.get("precio_unitario")
            ),
            proveedor_referencia=formulario.get("proveedor_referencia"),
            comprobante_referencia=formulario.get("comprobante_referencia"),
            observacion=formulario.get("observacion"),
            creado_por_usuario_id=usuario_id,
            InsumoPrecioVersion=modelos["InsumoPrecioVersion"],
            db_session=db_session,
        )
        return f"Precio de {insumo.nombre} actualizado a version {version.numero_version}."

    if accion == "crear_empleado":
        empleado = crear_empleado(
            **comunes,
            codigo=formulario.get("codigo"),
            nombre=formulario.get("nombre"),
            sector=formulario.get("sector"),
            puesto=formulario.get("puesto"),
            observacion=formulario.get("observacion"),
            EmpleadoProductivo=modelos["EmpleadoProductivo"],
            commit=False,
        )
        tarifa = registrar_costo_empleado(
            empleado,
            moneda=formulario.get("moneda", "ARS"),
            sueldo_base_centavos=importe_a_centavos(formulario.get("sueldo_base")),
            cargas_sociales_centavos=importe_a_centavos(
                formulario.get("cargas_sociales", 0)
            ),
            adicionales_centavos=importe_a_centavos(
                formulario.get("adicionales", 0)
            ),
            otros_costos_centavos=importe_a_centavos(
                formulario.get("otros_costos", 0)
            ),
            horas_mensuales=formulario.get("horas_mensuales"),
            horas_productivas=formulario.get("horas_productivas"),
            creado_por_usuario_id=usuario_id,
            EmpleadoCostoVersion=modelos["EmpleadoCostoVersion"],
            db_session=db_session,
        )
        return (
            f"Empleado {empleado.nombre} creado. "
            f"Costo por hora: ${tarifa.costo_hora_productiva_centavos / 100:.2f}."
        )

    if accion == "actualizar_costo_empleado":
        empleado = _registro_tenant(
            modelos["EmpleadoProductivo"],
            _id(formulario, "empleado_id"),
            organizacion.id,
            "El empleado",
            unidad_activa.id,
        )
        version = registrar_costo_empleado(
            empleado,
            moneda=formulario.get("moneda", "ARS"),
            sueldo_base_centavos=importe_a_centavos(formulario.get("sueldo_base")),
            cargas_sociales_centavos=importe_a_centavos(
                formulario.get("cargas_sociales", 0)
            ),
            adicionales_centavos=importe_a_centavos(
                formulario.get("adicionales", 0)
            ),
            otros_costos_centavos=importe_a_centavos(
                formulario.get("otros_costos", 0)
            ),
            horas_mensuales=formulario.get("horas_mensuales"),
            horas_productivas=formulario.get("horas_productivas"),
            observacion=formulario.get("observacion"),
            creado_por_usuario_id=usuario_id,
            EmpleadoCostoVersion=modelos["EmpleadoCostoVersion"],
            db_session=db_session,
        )
        return f"Costo laboral de {empleado.nombre} actualizado a version {version.numero_version}."

    if accion == "crear_costo_fijo":
        integra = formulario.get("integra_costo_produccion") == "1"
        costo = crear_costo_fijo(
            **comunes,
            codigo=formulario.get("codigo"),
            nombre=formulario.get("nombre"),
            categoria=formulario.get("categoria"),
            integra_costo_produccion=integra,
            criterio_distribucion=formulario.get("criterio_distribucion"),
            observacion=formulario.get("observacion"),
            CostoFijoProductivo=modelos["CostoFijoProductivo"],
            commit=False,
        )
        registrar_importe_costo_fijo(
            costo,
            moneda=formulario.get("moneda", "ARS"),
            importe_mensual_centavos=importe_a_centavos(
                formulario.get("importe_mensual")
            ),
            comprobante_referencia=formulario.get("comprobante_referencia"),
            creado_por_usuario_id=usuario_id,
            CostoFijoVersion=modelos["CostoFijoVersion"],
            db_session=db_session,
        )
        return f"Costo fijo {costo.nombre} creado con su importe inicial."

    if accion == "actualizar_importe_costo_fijo":
        costo = _registro_tenant(
            modelos["CostoFijoProductivo"],
            _id(formulario, "costo_fijo_id"),
            organizacion.id,
            "El costo fijo",
            unidad_activa.id,
        )
        version = registrar_importe_costo_fijo(
            costo,
            moneda=formulario.get("moneda", "ARS"),
            importe_mensual_centavos=importe_a_centavos(
                formulario.get("importe_mensual")
            ),
            comprobante_referencia=formulario.get("comprobante_referencia"),
            observacion=formulario.get("observacion"),
            creado_por_usuario_id=usuario_id,
            CostoFijoVersion=modelos["CostoFijoVersion"],
            db_session=db_session,
        )
        return f"Importe de {costo.nombre} actualizado a version {version.numero_version}."

    raise ValueError("Accion de fuente de costo no reconocida.")


def obtener_fuentes_costo(organizacion_id, unidad_negocio_id, *, modelos):
    perfiles = modelos["PerfilCosteoProducto"].query.filter_by(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id
    ).order_by(modelos["PerfilCosteoProducto"].fecha_creacion).all()
    Catalogo = modelos["Catalogo"]
    inclusiones = modelos["CatalogoProducto"].query.join(Catalogo).filter(
        Catalogo.organizacion_id == organizacion_id,
        Catalogo.unidad_negocio_id == unidad_negocio_id,
        modelos["CatalogoProducto"].activo.is_(True),
    ).order_by(modelos["CatalogoProducto"].nombre_comercial).all()
    return {
        "inclusiones_costeo": inclusiones,
        "perfiles_costeo": perfiles,
        "perfiles_combo": [perfil for perfil in perfiles if perfil.tipo == "combo"],
        "perfiles_componentes": [
            perfil for perfil in perfiles if perfil.tipo in {"simple", "produccion"}
        ],
        "perfiles_produccion": [perfil for perfil in perfiles if perfil.tipo == "produccion"],
        "insumos": modelos["InsumoProductivo"].query.filter(
            modelos["InsumoProductivo"].organizacion_id == organizacion_id,
            (modelos["InsumoProductivo"].unidad_negocio_id.is_(None))
            | (modelos["InsumoProductivo"].unidad_negocio_id == unidad_negocio_id),
        ).order_by(modelos["InsumoProductivo"].nombre).all(),
        "empleados": modelos["EmpleadoProductivo"].query.filter(
            modelos["EmpleadoProductivo"].organizacion_id == organizacion_id,
            (modelos["EmpleadoProductivo"].unidad_negocio_id.is_(None))
            | (modelos["EmpleadoProductivo"].unidad_negocio_id == unidad_negocio_id),
        ).order_by(modelos["EmpleadoProductivo"].nombre).all(),
        "costos_fijos": modelos["CostoFijoProductivo"].query.filter(
            modelos["CostoFijoProductivo"].organizacion_id == organizacion_id,
            (modelos["CostoFijoProductivo"].unidad_negocio_id.is_(None))
            | (modelos["CostoFijoProductivo"].unidad_negocio_id == unidad_negocio_id),
        ).order_by(modelos["CostoFijoProductivo"].nombre).all(),
    }
