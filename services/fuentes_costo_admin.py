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


def _id(formulario, campo, opcional=False):
    valor = str(formulario.get(campo) or "").strip()
    if opcional and not valor:
        return None
    if not valor.isdigit():
        raise ValueError(f"{campo} no es valido.")
    return int(valor)


def _registro_tenant(Modelo, registro_id, organizacion_id, nombre):
    registro = Modelo.query.filter_by(
        id=registro_id,
        organizacion_id=organizacion_id,
    ).first()
    if registro is None:
        raise ValueError(f"{nombre} no pertenece a la organizacion.")
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
    accion, formulario, *, organizacion, modelos, db_session, usuario,
):
    usuario_id = getattr(usuario, "id", None)
    comunes = _comunes(organizacion, modelos, db_session)
    comunes["unidad_negocio_id"] = _id(
        formulario, "unidad_negocio_id", opcional=True,
    )

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


def obtener_fuentes_costo(organizacion_id, *, modelos):
    return {
        "insumos": modelos["InsumoProductivo"].query.filter_by(
            organizacion_id=organizacion_id
        ).order_by(modelos["InsumoProductivo"].nombre).all(),
        "empleados": modelos["EmpleadoProductivo"].query.filter_by(
            organizacion_id=organizacion_id
        ).order_by(modelos["EmpleadoProductivo"].nombre).all(),
        "costos_fijos": modelos["CostoFijoProductivo"].query.filter_by(
            organizacion_id=organizacion_id
        ).order_by(modelos["CostoFijoProductivo"].nombre).all(),
    }
