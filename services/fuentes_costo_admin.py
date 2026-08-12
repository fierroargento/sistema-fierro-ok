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
from services.recursos_productivos import (
    configurar_integrantes,
    crear_recurso,
    recalcular_recursos_del_empleado,
    recalcular_tarifa_recurso,
    vincular_empleado,
)
from services.configuracion_costo_laboral import (
    configuracion_vigente,
    recalcular_empleados_generales,
    registrar_configuracion,
    validar_porcentaje,
)
from services.distribucion_laboral import (
    distribuciones_vigentes,
    registrar_distribucion,
)
from services.distribucion_costos_fijos import (
    distribuciones_costos_fijos_vigentes,
    registrar_distribucion_costo_fijo,
)
from services.ajustes_costos_ipc import (
    aprobar_propuesta, configurar_regla, ejecutar_ciclo_ipc,
    ventana_para_ajuste,
)
from services.cuentas_pagar_productivas import (
    crear_obligacion, registrar_pago, resumen_vencimientos, saldo_obligacion,
)


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

    if accion == "configurar_ajuste_ipc":
        costo = _registro_tenant(
            modelos["CostoFijoProductivo"], _id(formulario, "costo_fijo_id"),
            organizacion.id, "El costo indirecto", unidad_activa.id,
        )
        regla = configurar_regla(
            costo, proximo_ajuste=formulario.get("proximo_ajuste"),
            organizacion_id=organizacion.id, usuario_id=usuario_id,
            observacion=formulario.get("observacion"),
            ReglaAjusteIPCProductivo=modelos["ReglaAjusteIPCProductivo"],
            db_session=db_session,
        )
        ventana = ventana_para_ajuste(regla.proximo_ajuste)
        return (
            f"Ajuste IPC configurado. Ventana {ventana['inicio']:%m/%Y}–"
            f"{ventana['final']:%m/%Y}; vigencia {regla.proximo_ajuste:%d/%m/%Y}."
        )

    if accion == "actualizar_ipc":
        ejecutar_ciclo_ipc(modelos=modelos, db_session=db_session)
        return "IPC oficial consultado y propuestas actualizadas."

    if accion == "aprobar_ajuste_ipc":
        propuesta = modelos["PropuestaAjusteIPCProductivo"].query.filter_by(
            id=_id(formulario, "propuesta_id"),
        ).first()
        if propuesta is None or propuesta.regla.organizacion_id != organizacion.id:
            raise ValueError("La propuesta no pertenece a la organización.")
        aprobar_propuesta(
            propuesta, usuario_id=usuario_id,
            CostoFijoVersion=modelos["CostoFijoVersion"], db_session=db_session,
        )
        return "Ajuste aprobado; se aplicará en su fecha de vigencia."

    if accion == "crear_obligacion_costo":
        costo = _registro_tenant(
            modelos["CostoFijoProductivo"], _id(formulario, "costo_fijo_id"),
            organizacion.id, "El costo indirecto", unidad_activa.id,
        )
        obligacion = crear_obligacion(
            costo, periodo=formulario.get("periodo"),
            fecha_vencimiento=formulario.get("fecha_vencimiento"),
            importe_centavos=importe_a_centavos(formulario.get("importe")),
            organizacion_id=organizacion.id, usuario_id=usuario_id,
            observacion=formulario.get("observacion"),
            ObligacionCostoProductivo=modelos["ObligacionCostoProductivo"],
            CostoFijoVersion=modelos["CostoFijoVersion"], db_session=db_session,
        )
        return f"Obligación de {costo.nombre} creada para {obligacion.periodo:%m/%Y}."

    if accion == "registrar_pago_costo":
        obligacion = modelos["ObligacionCostoProductivo"].query.filter_by(
            id=_id(formulario, "obligacion_id"), organizacion_id=organizacion.id,
        ).first()
        if obligacion is None:
            raise ValueError("La obligación no pertenece a la organización.")
        registrar_pago(
            obligacion, fecha_pago=formulario.get("fecha_pago"),
            importe_centavos=importe_a_centavos(formulario.get("importe")),
            medio_pago=formulario.get("medio_pago"),
            referencia=formulario.get("referencia"),
            observacion=formulario.get("observacion"), usuario_id=usuario_id,
            PagoObligacionCostoProductivo=modelos["PagoObligacionCostoProductivo"],
            db_session=db_session,
        )
        return "Pago registrado y saldo actualizado."

    if accion == "configurar_distribucion_laboral":
        empleado = _registro_tenant(
            modelos["EmpleadoProductivo"],
            _id(formulario, "empleado_id"), organizacion.id,
            "El empleado", unidad_activa.id,
        )
        campos = zip(
            formulario.getlist("distribucion_unidad_id"),
            formulario.getlist("distribucion_porcentaje"),
            formulario.getlist("distribucion_ubicacion"),
            formulario.getlist("distribucion_funcion"),
        )
        filas = [
            {
                "unidad_negocio_id": unidad_id,
                "porcentaje_asignacion": porcentaje,
                "ubicacion_trabajo": ubicacion,
                "tipo_funcion": funcion,
            }
            for unidad_id, porcentaje, ubicacion, funcion in campos
        ]
        unidades = modelos["UnidadNegocio"].query.filter_by(
            organizacion_id=organizacion.id,
        ).all()
        revision, _creadas = registrar_distribucion(
            empleado, filas,
            organizacion_id=organizacion.id,
            unidades_validas=unidades,
            Modelo=modelos["EmpleadoDistribucionVersion"],
            db_session=db_session,
            usuario_id=usuario_id,
            observacion=formulario.get("observacion_distribucion"),
        )
        return f"Distribución de {empleado.nombre} guardada en revisión {revision}."

    if accion == "configurar_distribucion_costo_fijo":
        costo = _registro_tenant(
            modelos["CostoFijoProductivo"],
            _id(formulario, "costo_fijo_id"), organizacion.id,
            "El costo fijo", unidad_activa.id,
        )
        filas = [
            {
                "unidad_negocio_id": unidad_id,
                "porcentaje_asignacion": porcentaje,
                "ubicacion_costo": ubicacion,
                "porcentaje_productivo": productivo,
            }
            for unidad_id, porcentaje, ubicacion, productivo in zip(
                formulario.getlist("costo_unidad_id"),
                formulario.getlist("costo_porcentaje_asignacion"),
                formulario.getlist("costo_ubicacion"),
                formulario.getlist("costo_porcentaje_productivo"),
            )
        ]
        unidades = modelos["UnidadNegocio"].query.filter_by(
            organizacion_id=organizacion.id,
        ).all()
        if costo.unidad_negocio_id is not None:
            unidades = [
                unidad for unidad in unidades
                if unidad.id == costo.unidad_negocio_id
            ]
        revision, _creadas = registrar_distribucion_costo_fijo(
            costo, filas, organizacion_id=organizacion.id,
            unidades_validas=unidades,
            Modelo=modelos["CostoFijoDistribucionVersion"],
            db_session=db_session, usuario_id=usuario_id,
            observacion=formulario.get("observacion_distribucion_costo"),
        )
        return f"Distribución de {costo.nombre} guardada en revisión {revision}."

    if accion == "configurar_porcentaje_costo_laboral":
        version = registrar_configuracion(
            organizacion_id=organizacion.id,
            unidad_negocio_id=unidad_activa.id,
            porcentaje=formulario.get("porcentaje_cargas_general"),
            observacion=formulario.get("observacion"),
            usuario_id=usuario_id,
            Modelo=modelos["ConfiguracionCostoLaboralVersion"],
            db_session=db_session,
        )
        empleados = modelos["EmpleadoProductivo"].query.filter_by(
            organizacion_id=organizacion.id,
            unidad_negocio_id=unidad_activa.id,
            tipo_registro="empleado",
        ).all()
        cantidad = recalcular_empleados_generales(
            empleados, version.porcentaje_cargas,
            EmpleadoCostoVersion=modelos["EmpleadoCostoVersion"],
            db_session=db_session, usuario_id=usuario_id,
        )
        return (
            f"Porcentaje general actualizado a {version.porcentaje_cargas}%. "
            f"{cantidad} empleados recalculados."
        )

    if accion == "crear_recurso_productivo":
        recurso = crear_recurso(
            **comunes,
            codigo=formulario.get("codigo"),
            nombre=formulario.get("nombre"),
            sector=formulario.get("sector"),
            porcentaje_indirecto=formulario.get("porcentaje_indirecto", 0),
            observacion=formulario.get("observacion"),
            EmpleadoProductivo=modelos["EmpleadoProductivo"],
        )
        return f"Recurso productivo {recurso.nombre} creado."

    if accion in {
        "configurar_integrantes_recurso",
        "vincular_empleado_recurso", "recalcular_recurso_productivo",
        "desvincular_empleado_recurso",
    }:
        recurso = _registro_tenant(
            modelos["EmpleadoProductivo"],
            _id(formulario, "recurso_id"), organizacion.id,
            "El recurso", unidad_activa.id,
        )
        if recurso.tipo_registro != "recurso":
            raise ValueError("El registro seleccionado no es un recurso productivo.")
        if accion == "configurar_integrantes_recurso":
            empleados = []
            for empleado_id in formulario.getlist("integrante_seleccionado"):
                if not str(empleado_id).isdigit():
                    raise ValueError("El empleado seleccionado no es válido.")
                empleado = _registro_tenant(
                    modelos["EmpleadoProductivo"], int(empleado_id),
                    organizacion.id, "El empleado", unidad_activa.id,
                )
                empleados.append((
                    empleado,
                    formulario.get(f"integrante_dedicacion_{empleado_id}"),
                ))
            resultado = configurar_integrantes(
                recurso, empleados,
                porcentaje_indirecto=formulario.get(
                    "porcentaje_indirecto", recurso.porcentaje_indirecto,
                ),
                RecursoEmpleadoProductivo=modelos["RecursoEmpleadoProductivo"],
                db_session=db_session,
            )
            if resultado["integrantes"]:
                version, _valores = recalcular_tarifa_recurso(
                    recurso,
                    EmpleadoCostoVersion=modelos["EmpleadoCostoVersion"],
                    db_session=db_session, usuario_id=usuario_id,
                )
                tarifa = (
                    f" Tarifa actualizada a "
                    f"${version.costo_hora_productiva_centavos / 100:.2f}/h."
                )
            else:
                for version in recurso.versiones_costo:
                    if version.vigente:
                        version.vigente = False
                db_session.commit()
                tarifa = " El recurso quedó sin tarifa vigente."
            return (
                f"Equipo de {recurso.nombre} guardado con "
                f"{resultado['integrantes']} integrantes.{tarifa}"
            )
        if accion == "vincular_empleado_recurso":
            empleado = _registro_tenant(
                modelos["EmpleadoProductivo"],
                _id(formulario, "empleado_id"), organizacion.id,
                "El empleado", unidad_activa.id,
            )
            vincular_empleado(
                recurso, empleado,
                porcentaje_dedicacion=formulario.get("porcentaje_dedicacion", 100),
                observacion=formulario.get("observacion"),
                RecursoEmpleadoProductivo=modelos["RecursoEmpleadoProductivo"],
                db_session=db_session,
            )
            version, _valores = recalcular_tarifa_recurso(
                recurso,
                EmpleadoCostoVersion=modelos["EmpleadoCostoVersion"],
                db_session=db_session, usuario_id=usuario_id,
            )
            return (
                f"{empleado.nombre} incorporado a {recurso.nombre}. "
                f"Tarifa: ${version.costo_hora_productiva_centavos / 100:.2f}/h."
            )
        if accion == "desvincular_empleado_recurso":
            vinculo = modelos["RecursoEmpleadoProductivo"].query.filter_by(
                id=_id(formulario, "vinculo_id"), recurso_id=recurso.id,
            ).first()
            if vinculo is None:
                raise ValueError("La asignación no pertenece al recurso.")
            db_session.delete(vinculo)
            db_session.commit()
            if recurso.miembros_recurso:
                recalcular_tarifa_recurso(
                    recurso,
                    EmpleadoCostoVersion=modelos["EmpleadoCostoVersion"],
                    db_session=db_session, usuario_id=usuario_id,
                )
            return "Empleado retirado del recurso productivo."
        recurso.porcentaje_indirecto = formulario.get(
            "porcentaje_indirecto", recurso.porcentaje_indirecto,
        )
        version, _valores = recalcular_tarifa_recurso(
            recurso,
            EmpleadoCostoVersion=modelos["EmpleadoCostoVersion"],
            db_session=db_session, usuario_id=usuario_id,
        )
        return (
            f"Tarifa de {recurso.nombre} actualizada: "
            f"${version.costo_hora_productiva_centavos / 100:.2f}/h."
        )

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
            recurso = _registro_tenant(
                modelos["EmpleadoProductivo"],
                _id(
                    formulario,
                    "recurso_laboral_id"
                    if formulario.get("recurso_laboral_id")
                    else "empleado_id",
                ),
                organizacion.id, "El recurso laboral", unidad_activa.id,
            )
            guardar_operacion(perfil, recurso, nombre=formulario.get("nombre_operacion"), minutos=formulario.get("minutos"), observacion=formulario.get("observacion"), Modelo=modelos["ProductoOperacionCosteo"], db_session=db_session, registro_id=formulario.get("operacion_id"))
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
        if formulario.get("nombre") is not None:
            insumo.nombre = str(formulario.get("nombre") or "").strip()
        if formulario.get("tipo") is not None:
            tipo = str(formulario.get("tipo") or "").strip().lower()
            if tipo not in {"materia_prima", "consumible", "servicio_productivo", "embalaje_productivo"}:
                raise ValueError("El tipo de insumo no es valido.")
            insumo.tipo = tipo
        if formulario.get("unidad_medida") is not None:
            insumo.unidad_medida = str(formulario.get("unidad_medida") or "").strip()
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
        excepcion = str(formulario.get("porcentaje_cargas") or "").strip()
        general = configuracion_vigente(
            organizacion.id, unidad_activa.id,
            Modelo=modelos["ConfiguracionCostoLaboralVersion"],
        )
        porcentaje = validar_porcentaje(
            excepcion if excepcion else general.porcentaje_cargas if general else 0
        )
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
            porcentaje_cargas=porcentaje,
            usa_porcentaje_general=not bool(excepcion),
            adicionales_centavos=importe_a_centavos(
                formulario.get("adicionales", 0)
            ),
            otros_costos_centavos=importe_a_centavos(
                formulario.get("otros_costos", 0)
            ),
            horas_mensuales=formulario.get("horas_mensuales"),
            horas_productivas=formulario.get("horas_productivas"),
            ubicacion_trabajo=formulario.get("ubicacion_trabajo", "Sin definir"),
            tipo_funcion=formulario.get("tipo_funcion", "directa"),
            porcentaje_productivo=formulario.get("porcentaje_productivo", 100),
            creado_por_usuario_id=usuario_id,
            EmpleadoCostoVersion=modelos["EmpleadoCostoVersion"],
            db_session=db_session,
        )
        recalcular_recursos_del_empleado(
            empleado,
            EmpleadoCostoVersion=modelos["EmpleadoCostoVersion"],
            db_session=db_session, usuario_id=usuario_id,
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
        if formulario.get("nombre") is not None:
            empleado.nombre = str(formulario.get("nombre") or "").strip()
        if formulario.get("sector") is not None:
            empleado.sector = str(formulario.get("sector") or "").strip()
        if formulario.get("puesto") is not None:
            empleado.puesto = str(formulario.get("puesto") or "").strip() or None
        excepcion = str(formulario.get("porcentaje_cargas") or "").strip()
        general = configuracion_vigente(
            organizacion.id, unidad_activa.id,
            Modelo=modelos["ConfiguracionCostoLaboralVersion"],
        )
        porcentaje = validar_porcentaje(
            excepcion if excepcion else general.porcentaje_cargas if general else 0
        )
        version = registrar_costo_empleado(
            empleado,
            moneda=formulario.get("moneda", "ARS"),
            sueldo_base_centavos=importe_a_centavos(formulario.get("sueldo_base")),
            porcentaje_cargas=porcentaje,
            usa_porcentaje_general=not bool(excepcion),
            adicionales_centavos=importe_a_centavos(
                formulario.get("adicionales", 0)
            ),
            otros_costos_centavos=importe_a_centavos(
                formulario.get("otros_costos", 0)
            ),
            horas_mensuales=formulario.get("horas_mensuales"),
            horas_productivas=formulario.get("horas_productivas"),
            ubicacion_trabajo=formulario.get("ubicacion_trabajo", "Sin definir"),
            tipo_funcion=formulario.get("tipo_funcion", "directa"),
            porcentaje_productivo=formulario.get("porcentaje_productivo", 100),
            observacion=formulario.get("observacion"),
            creado_por_usuario_id=usuario_id,
            EmpleadoCostoVersion=modelos["EmpleadoCostoVersion"],
            db_session=db_session,
        )
        recalcular_recursos_del_empleado(
            empleado,
            EmpleadoCostoVersion=modelos["EmpleadoCostoVersion"],
            db_session=db_session, usuario_id=usuario_id,
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
            importe_periodo_centavos=importe_a_centavos(
                formulario.get("importe_periodo", formulario.get("importe_mensual"))
            ),
            naturaleza=formulario.get("naturaleza", "fijo"),
            periodicidad=formulario.get("periodicidad", "mensual"),
            meses_cobertura=formulario.get("meses_cobertura"),
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
        if formulario.get("nombre") is not None:
            costo.nombre = str(formulario.get("nombre") or "").strip()
        if formulario.get("categoria") is not None:
            costo.categoria = str(formulario.get("categoria") or "").strip()
        if formulario.get("integra_costo_produccion") is not None:
            integra = formulario.get("integra_costo_produccion") == "1"
            criterio = str(formulario.get("criterio_distribucion") or "").strip().lower()
            permitidos = {"horas_productivas", "horas_maquina", "unidades_producidas", "porcentaje", "importe_directo", "sin_distribuir"}
            if criterio not in permitidos:
                raise ValueError("El criterio de distribucion no es valido.")
            if not integra and criterio != "sin_distribuir":
                raise ValueError("Un costo que no integra produccion debe quedar sin distribuir.")
            costo.integra_costo_produccion = integra
            costo.criterio_distribucion = criterio
        version = registrar_importe_costo_fijo(
            costo,
            moneda=formulario.get("moneda", "ARS"),
            importe_periodo_centavos=importe_a_centavos(
                formulario.get("importe_periodo", formulario.get("importe_mensual"))
            ),
            naturaleza=formulario.get("naturaleza", "fijo"),
            periodicidad=formulario.get("periodicidad", "mensual"),
            meses_cobertura=formulario.get("meses_cobertura"),
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
    empleados = modelos["EmpleadoProductivo"].query.filter(
        modelos["EmpleadoProductivo"].organizacion_id == organizacion_id,
        modelos["EmpleadoProductivo"].tipo_registro == "empleado",
        (modelos["EmpleadoProductivo"].unidad_negocio_id.is_(None))
        | (modelos["EmpleadoProductivo"].unidad_negocio_id == unidad_negocio_id),
    ).order_by(modelos["EmpleadoProductivo"].nombre).all()
    costos_fijos = modelos["CostoFijoProductivo"].query.filter(
        modelos["CostoFijoProductivo"].organizacion_id == organizacion_id,
        (modelos["CostoFijoProductivo"].unidad_negocio_id.is_(None))
        | (modelos["CostoFijoProductivo"].unidad_negocio_id == unidad_negocio_id),
    ).order_by(modelos["CostoFijoProductivo"].nombre).all()
    ids_costos_visibles = [costo.id for costo in costos_fijos]
    reglas_ipc = modelos["ReglaAjusteIPCProductivo"].query.filter_by(
        organizacion_id=organizacion_id, activa=True,
    ).filter(
        modelos["ReglaAjusteIPCProductivo"].costo_fijo_id.in_(ids_costos_visibles)
    ).all() if ids_costos_visibles else []
    reglas_por_costo = {regla.costo_fijo_id: regla for regla in reglas_ipc}
    propuestas = modelos["PropuestaAjusteIPCProductivo"].query.join(
        modelos["ReglaAjusteIPCProductivo"],
    ).filter(
        modelos["ReglaAjusteIPCProductivo"].organizacion_id == organizacion_id,
        modelos["PropuestaAjusteIPCProductivo"].estado.in_(("pendiente", "aprobada")),
        modelos["ReglaAjusteIPCProductivo"].costo_fijo_id.in_(ids_costos_visibles),
    ).all() if ids_costos_visibles else []
    obligaciones = modelos["ObligacionCostoProductivo"].query.filter_by(
        organizacion_id=organizacion_id,
    ).filter(
        modelos["ObligacionCostoProductivo"].costo_fijo_id.in_(ids_costos_visibles),
    ).order_by(
        modelos["ObligacionCostoProductivo"].fecha_vencimiento.desc(),
    ).all() if ids_costos_visibles else []
    return {
        "configuracion_costo_laboral": configuracion_vigente(
            organizacion_id, unidad_negocio_id,
            Modelo=modelos["ConfiguracionCostoLaboralVersion"],
        ),
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
        "empleados": empleados,
        "distribuciones_laborales": distribuciones_vigentes(
            empleados, Modelo=modelos["EmpleadoDistribucionVersion"],
        ),
        "recursos_productivos": modelos["EmpleadoProductivo"].query.filter(
            modelos["EmpleadoProductivo"].organizacion_id == organizacion_id,
            modelos["EmpleadoProductivo"].tipo_registro == "recurso",
            (modelos["EmpleadoProductivo"].unidad_negocio_id.is_(None))
            | (modelos["EmpleadoProductivo"].unidad_negocio_id == unidad_negocio_id),
        ).order_by(modelos["EmpleadoProductivo"].nombre).all(),
        "costos_fijos": costos_fijos,
        "distribuciones_costos_fijos": distribuciones_costos_fijos_vigentes(
            costos_fijos, Modelo=modelos["CostoFijoDistribucionVersion"],
        ),
        "reglas_ipc_por_costo": reglas_por_costo,
        "propuestas_ipc": propuestas,
        "obligaciones_costos": obligaciones,
        "avisos_vencimientos": resumen_vencimientos(obligaciones),
        "saldo_obligacion": saldo_obligacion,
        "ventana_para_ajuste": ventana_para_ajuste,
    }
