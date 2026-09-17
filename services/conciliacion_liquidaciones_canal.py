"""Calcula y concilia ventas con movimientos internos, sin proveedores externos."""

from io import BytesIO

from openpyxl import Workbook

from services.motor_comercial_canal import liquidar_precio


CLASIFICACIONES_GESTION = {
    "pago_pendiente", "pago_incompleto", "cobro_mayor", "bajo_piso",
    "devolucion", "anulacion", "dato_inconsistente", "ajuste_aceptado",
    "sin_diferencia",
}
ESTADOS_GESTION = {"en_revision", "resuelta", "descartada"}


def calcular_expectativa(precio_unitario_centavos, cantidad, regla_canal):
    cantidad = int(cantidad); precio = int(precio_unitario_centavos)
    if cantidad <= 0 or precio < 0: raise ValueError("La cantidad y el precio no son validos.")
    unidad = liquidar_precio(
        precio, comision_pct=regla_canal.comision_pct,
        publicidad_pct=getattr(regla_canal, "publicidad_pct", 0),
        financiacion_pct=getattr(regla_canal, "financiacion_pct", 0),
        devoluciones_pct=getattr(regla_canal, "devoluciones_pct", 0),
        tramos=regla_canal.tramos,
        umbral_envio_centavos=regla_canal.umbral_envio_centavos,
        costo_envio_centavos=regla_canal.costo_envio_default_centavos,
    )
    return {
        "importe_bruto_centavos": precio * cantidad,
        "comision_esperada_centavos": unidad["comision_centavos"] * cantidad,
        "publicidad_esperada_centavos": unidad["publicidad_centavos"] * cantidad,
        "financiacion_esperada_centavos": unidad["financiacion_centavos"] * cantidad,
        "devoluciones_esperadas_centavos": unidad["devoluciones_centavos"] * cantidad,
        "cargo_fijo_esperado_centavos": unidad["cargo_fijo_centavos"] * cantidad,
        "envio_esperado_centavos": unidad["envio_centavos"] * cantidad,
        "liquidacion_esperada_centavos": unidad["liquidacion_centavos"] * cantidad,
    }


def registrar_venta(*, organizacion_id, unidad_negocio_id, lista_precio_id,
                    catalogo_producto_id, cuenta_codigo, referencia_venta,
                    referencia_item, referencia_pago, cantidad,
                    precio_unitario_centavos, estado, fecha_venta, regla_canal,
                    costo_unitario_centavos=None, piso_unitario_centavos=None,
                    origen="manual", usuario=None, VentaCanalItem=None,
                    db_session=None, commit=True):
    estado = str(estado or "confirmada").strip().lower()
    if estado not in {"confirmada", "cancelada", "devuelta", "devolucion_parcial"}: raise ValueError("El estado de venta no es valido.")
    cuenta = str(cuenta_codigo or "").strip(); venta = str(referencia_venta or "").strip(); item = str(referencia_item or "").strip()
    if not cuenta or not venta or not item: raise ValueError("Falta la identidad de cuenta, venta o item.")
    expectativa = calcular_expectativa(precio_unitario_centavos, cantidad, regla_canal)
    registro = VentaCanalItem(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
        lista_precio_id=lista_precio_id, catalogo_producto_id=catalogo_producto_id,
        cuenta_codigo=cuenta, referencia_venta=venta, referencia_item=item,
        referencia_pago=str(referencia_pago or "").strip() or None,
        cantidad=int(cantidad), precio_unitario_centavos=int(precio_unitario_centavos),
        estado=estado, fecha_venta=fecha_venta, origen=origen,
        costo_unitario_snapshot_centavos=costo_unitario_centavos,
        piso_unitario_snapshot_centavos=piso_unitario_centavos,
        creado_por_usuario_id=getattr(usuario, "id", None),
        creado_por_username=getattr(usuario, "username", None), **expectativa,
    )
    db_session.add(registro)
    if commit: db_session.commit()
    return registro


def registrar_movimiento(*, organizacion_id, unidad_negocio_id, cuenta_codigo,
                         referencia_venta, referencia_pago, referencia_movimiento,
                         tipo, direccion, importe_centavos, fecha_movimiento,
                         impacta_saldo=True, estado="confirmado", detalle=None,
                         origen="manual", usuario=None,
                         MovimientoLiquidacionCanal=None, db_session=None,
                         commit=True):
    tipo = str(tipo or "").strip().lower(); direccion = str(direccion or "").strip().lower()
    permitidos = {"pago_bruto", "liquidacion_neta", "comision", "cargo_fijo", "envio", "impuesto", "retencion", "devolucion", "ajuste"}
    if tipo not in permitidos or direccion not in {"credito", "debito"}: raise ValueError("El tipo o la direccion del movimiento no son validos.")
    importe = int(importe_centavos)
    if importe < 0: raise ValueError("El importe no puede ser negativo.")
    registro = MovimientoLiquidacionCanal(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
        cuenta_codigo=str(cuenta_codigo or "").strip(), referencia_venta=str(referencia_venta or "").strip(),
        referencia_pago=str(referencia_pago or "").strip() or None,
        referencia_movimiento=str(referencia_movimiento or "").strip(), tipo=tipo,
        direccion=direccion, importe_centavos=importe, impacta_saldo=bool(impacta_saldo),
        estado=str(estado or "confirmado").strip(), fecha_movimiento=fecha_movimiento,
        detalle=str(detalle or "").strip() or None, origen=origen,
        creado_por_usuario_id=getattr(usuario, "id", None), creado_por_username=getattr(usuario, "username", None),
    )
    if not registro.cuenta_codigo or not registro.referencia_venta or not registro.referencia_movimiento: raise ValueError("Falta la identidad del movimiento.")
    db_session.add(registro)
    if commit: db_session.commit()
    return registro


def conciliar_venta(referencia_venta, cuenta_codigo, ventas, movimientos, *, tolerancia_centavos=1):
    items = [v for v in ventas if v.referencia_venta == referencia_venta and v.cuenta_codigo == cuenta_codigo]
    propios = [m for m in movimientos if m.referencia_venta == referencia_venta and m.cuenta_codigo == cuenta_codigo and m.impacta_saldo and m.estado != "anulado"]
    esperado = sum(int(v.liquidacion_esperada_centavos) for v in items if v.estado not in {"cancelada", "devuelta"})
    pisos = [int(v.piso_unitario_snapshot_centavos) * int(v.cantidad) for v in items if v.estado not in {"cancelada", "devuelta"} and v.piso_unitario_snapshot_centavos is not None]
    piso = sum(pisos) if pisos else None
    bruto = sum(int(v.importe_bruto_centavos) for v in items)
    deducciones = {
        "comision_esperada_centavos": sum(int(getattr(v, "comision_esperada_centavos", 0) or 0) for v in items),
        "publicidad_esperada_centavos": sum(int(getattr(v, "publicidad_esperada_centavos", 0) or 0) for v in items),
        "financiacion_esperada_centavos": sum(int(getattr(v, "financiacion_esperada_centavos", 0) or 0) for v in items),
        "devoluciones_esperadas_centavos": sum(int(getattr(v, "devoluciones_esperadas_centavos", 0) or 0) for v in items),
        "cargo_fijo_esperado_centavos": sum(int(getattr(v, "cargo_fijo_esperado_centavos", 0) or 0) for v in items),
        "envio_esperado_centavos": sum(int(getattr(v, "envio_esperado_centavos", 0) or 0) for v in items),
    }
    real = sum(int(m.importe_centavos) * (1 if m.direccion == "credito" else -1) for m in propios)
    estados = {v.estado for v in items}
    if items and estados <= {"cancelada"}: estado = "anulada"
    elif items and estados <= {"devuelta"}: estado = "devuelta"
    elif "devolucion_parcial" in estados: estado = "devolucion_parcial"
    elif not propios: estado = "pendiente"
    elif real < esperado - int(tolerancia_centavos): estado = "pago_parcial"
    elif real > esperado + int(tolerancia_centavos): estado = "diferencia_a_favor"
    else: estado = "conciliada"
    estado_economico = "no_aplica" if estados and estados <= {"cancelada", "devuelta"} else "sin_piso" if piso is None else "cumple" if esperado >= piso else "bajo_piso"
    return {"referencia_venta": referencia_venta, "cuenta_codigo": cuenta_codigo, "items": items, "movimientos": propios, "importe_bruto_centavos": bruto, **deducciones, "liquidacion_esperada_centavos": esperado, "piso_economico_centavos": piso, "estado_economico": estado_economico, "liquidacion_real_centavos": real, "diferencia_centavos": real - esperado, "estado_conciliacion": estado}


def construir_conciliaciones(ventas, movimientos, *, tolerancia_centavos=1):
    claves = sorted({(v.cuenta_codigo, v.referencia_venta) for v in ventas})
    filas = [conciliar_venta(venta, cuenta, ventas, movimientos, tolerancia_centavos=tolerancia_centavos) for cuenta, venta in claves]
    estados = ("conciliada", "pendiente", "pago_parcial", "diferencia_a_favor", "anulada", "devuelta", "devolucion_parcial")
    resumen = {estado: 0 for estado in estados}; resumen["total"] = len(filas); resumen["bajo_piso"] = 0
    for fila in filas:
        resumen[fila["estado_conciliacion"]] += 1
        if fila["estado_economico"] == "bajo_piso": resumen["bajo_piso"] += 1
    return filas, resumen


def clasificar_caso(fila):
    if fila["estado_economico"] == "bajo_piso": return "bajo_piso"
    return {
        "pendiente": "pago_pendiente",
        "pago_parcial": "pago_incompleto",
        "diferencia_a_favor": "cobro_mayor",
        "devuelta": "devolucion",
        "devolucion_parcial": "devolucion",
        "anulada": "anulacion",
        "conciliada": "sin_diferencia",
    }.get(fila["estado_conciliacion"], "dato_inconsistente")


def incorporar_gestiones(filas, gestiones):
    """Agrega la ultima decision sin modificar el calculo financiero original."""
    ultimas = {}
    for gestion in sorted(gestiones, key=lambda g: (getattr(g, "fecha_registro", None), getattr(g, "id", 0))):
        ultimas[(gestion.cuenta_codigo, gestion.referencia_venta)] = gestion
    for fila in filas:
        gestion = ultimas.get((fila["cuenta_codigo"], fila["referencia_venta"]))
        fila["clasificacion_sugerida"] = clasificar_caso(fila)
        fila["gestion_actual"] = gestion
        fila["estado_gestion"] = getattr(gestion, "estado", "abierta")
        fila["requiere_revision"] = fila["estado_conciliacion"] not in {"conciliada", "anulada"} or fila["estado_economico"] == "bajo_piso"
    return filas


def registrar_gestion(fila, *, clasificacion, estado, observacion, organizacion_id,
                      unidad_negocio_id, usuario, GestionConciliacionCanal,
                      db_session, commit=True):
    clasificacion = str(clasificacion or "").strip().lower()
    estado = str(estado or "").strip().lower()
    observacion = str(observacion or "").strip()
    if clasificacion not in CLASIFICACIONES_GESTION: raise ValueError("La clasificacion del caso no es valida.")
    if estado not in ESTADOS_GESTION: raise ValueError("El estado de gestion no es valido.")
    if estado in {"resuelta", "descartada"} and not observacion: raise ValueError("La observacion es obligatoria para cerrar el caso.")
    registro = GestionConciliacionCanal(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
        cuenta_codigo=fila["cuenta_codigo"], referencia_venta=fila["referencia_venta"],
        clasificacion=clasificacion, estado=estado, observacion=observacion or None,
        liquidacion_esperada_snapshot_centavos=fila["liquidacion_esperada_centavos"],
        liquidacion_real_snapshot_centavos=fila["liquidacion_real_centavos"],
        diferencia_snapshot_centavos=fila["diferencia_centavos"],
        creado_por_usuario_id=getattr(usuario, "id", None),
        creado_por_username=getattr(usuario, "username", None),
    )
    db_session.add(registro)
    if commit: db_session.commit()
    return registro


def exportar_conciliaciones(filas):
    libro = Workbook(); hoja = libro.active; hoja.title = "Conciliacion"
    hoja.append(["CUENTA", "VENTA", "ESTADO", "CONTROL_ECONOMICO", "CLASIFICACION", "ESTADO_GESTION", "OBSERVACION", "BRUTO", "COMISION_ESPERADA", "PUBLICIDAD_ESPERADA", "FINANCIACION_ESPERADA", "DEVOLUCIONES_ESPERADAS", "CARGO_FIJO_ESPERADO", "ENVIO_ESPERADO", "ESPERADO", "PISO", "REAL", "DIFERENCIA", "ITEMS", "MOVIMIENTOS"])
    for fila in filas:
        hoja.append([
            fila["cuenta_codigo"], fila["referencia_venta"], fila["estado_conciliacion"],
            fila["estado_economico"], fila.get("clasificacion_sugerida"),
            fila.get("estado_gestion", "abierta"),
            getattr(fila.get("gestion_actual"), "observacion", None),
            fila["importe_bruto_centavos"] / 100,
            fila["comision_esperada_centavos"] / 100,
            fila["publicidad_esperada_centavos"] / 100,
            fila["financiacion_esperada_centavos"] / 100,
            fila["devoluciones_esperadas_centavos"] / 100,
            fila["cargo_fijo_esperado_centavos"] / 100,
            fila["envio_esperado_centavos"] / 100,
            fila["liquidacion_esperada_centavos"] / 100,
            fila["piso_economico_centavos"] / 100 if fila["piso_economico_centavos"] is not None else None,
            fila["liquidacion_real_centavos"] / 100, fila["diferencia_centavos"] / 100,
            len(fila["items"]), len(fila["movimientos"]),
        ])
    hoja.freeze_panes = "A2"; salida = BytesIO(); libro.save(salida); salida.seek(0); return salida
