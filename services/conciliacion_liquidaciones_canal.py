"""Calcula y concilia ventas con movimientos internos, sin proveedores externos."""

from services.motor_comercial_canal import liquidar_precio


def calcular_expectativa(precio_unitario_centavos, cantidad, regla_canal):
    cantidad = int(cantidad); precio = int(precio_unitario_centavos)
    if cantidad <= 0 or precio < 0: raise ValueError("La cantidad y el precio no son validos.")
    unidad = liquidar_precio(
        precio, comision_pct=regla_canal.comision_pct, tramos=regla_canal.tramos,
        umbral_envio_centavos=regla_canal.umbral_envio_centavos,
        costo_envio_centavos=regla_canal.costo_envio_default_centavos,
    )
    return {
        "importe_bruto_centavos": precio * cantidad,
        "comision_esperada_centavos": unidad["comision_centavos"] * cantidad,
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
    return {"referencia_venta": referencia_venta, "cuenta_codigo": cuenta_codigo, "items": items, "movimientos": propios, "importe_bruto_centavos": bruto, "liquidacion_esperada_centavos": esperado, "piso_economico_centavos": piso, "estado_economico": estado_economico, "liquidacion_real_centavos": real, "diferencia_centavos": real - esperado, "estado_conciliacion": estado}


def construir_conciliaciones(ventas, movimientos, *, tolerancia_centavos=1):
    claves = sorted({(v.cuenta_codigo, v.referencia_venta) for v in ventas})
    filas = [conciliar_venta(venta, cuenta, ventas, movimientos, tolerancia_centavos=tolerancia_centavos) for cuenta, venta in claves]
    estados = ("conciliada", "pendiente", "pago_parcial", "diferencia_a_favor", "anulada", "devuelta", "devolucion_parcial")
    resumen = {estado: 0 for estado in estados}; resumen["total"] = len(filas); resumen["bajo_piso"] = 0
    for fila in filas:
        resumen[fila["estado_conciliacion"]] += 1
        if fila["estado_economico"] == "bajo_piso": resumen["bajo_piso"] += 1
    return filas, resumen
