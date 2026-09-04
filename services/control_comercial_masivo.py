"""Bandeja diagnostica de rentabilidad por producto y canal, sin ejecucion."""

from io import BytesIO
from decimal import Decimal

from openpyxl import Workbook

from services.motor_comercial_canal import liquidar_precio


def evaluar_control(simulacion, precio_actual_centavos=None, fuente_precio=None,
                    promocion=None, precio_base_centavos=None):
    minimo = simulacion["minimo"]
    objetivo = simulacion["objetivo"]
    piso_minimo = minimo["piso_liquidacion_centavos"]
    piso_objetivo = objetivo["piso_liquidacion_centavos"]
    regla = simulacion["regla_canal"]
    actual = None
    if precio_actual_centavos is not None:
        actual = liquidar_precio(
            int(precio_actual_centavos), comision_pct=regla.comision_pct,
            tramos=regla.tramos,
            umbral_envio_centavos=regla.umbral_envio_centavos,
            costo_envio_centavos=regla.costo_envio_default_centavos,
        )
    if actual is None:
        estado = "sin_precio"
    elif actual["liquidacion_centavos"] < piso_minimo:
        estado = "debajo_del_piso"
    elif actual["liquidacion_centavos"] < piso_objetivo:
        estado = "al_limite"
    else:
        estado = "rentable"
    precio_propuesto = objetivo["precio_final_centavos"]
    if actual is not None and actual["precio_final_centavos"] >= precio_propuesto:
        precio_propuesto = actual["precio_final_centavos"]
    propuesto = liquidar_precio(
        precio_propuesto, comision_pct=regla.comision_pct,
        tramos=regla.tramos,
        umbral_envio_centavos=regla.umbral_envio_centavos,
        costo_envio_centavos=regla.costo_envio_default_centavos,
    )
    requiere_correccion = actual is None or precio_propuesto > actual["precio_final_centavos"]
    promocion_activa = promocion is not None and promocion.estado_observado == "activa"
    accion_recomendada = (
        "completar_catalogo" if simulacion.get("inclusion") is None else
        "cancelar_promocion_antes_de_actualizar" if promocion_activa and requiere_correccion
        else "mantener_promocion" if promocion_activa else
        "actualizar_precio" if requiere_correccion else "sin_accion"
    )
    return {
        **simulacion, "estado_control": estado, "actual": actual,
        "fuente_precio": fuente_precio or ("sin_precio" if actual is None else "interno"),
        "propuesto": propuesto,
        "diferencia_precio_centavos": None if actual is None else precio_propuesto - actual["precio_final_centavos"],
        "diferencia_pct": None if actual is None or not actual["precio_final_centavos"] else round((precio_propuesto - actual["precio_final_centavos"]) * 100 / actual["precio_final_centavos"], 2),
        "cambia_cargo": actual is not None and actual["cargo_fijo_centavos"] != propuesto["cargo_fijo_centavos"],
        "cambia_envio": actual is not None and actual["envio_centavos"] != propuesto["envio_centavos"],
        "promocion": promocion, "promocion_activa": promocion_activa,
        "precio_base_centavos": precio_base_centavos,
        "accion_recomendada": accion_recomendada,
        "clave": f'{regla.lista_precio_id}:{simulacion["costo"].producto_id}',
    }


def construir_bandeja(simulaciones, items, promociones=(), observaciones=()):
    from services.promociones_canal import observaciones_actuales
    promociones_por_clave = observaciones_actuales(promociones)
    observaciones_por_clave = {}
    for observacion in observaciones:
        clave_observacion = (observacion.lista_precio_id, observacion.catalogo_producto_id, observacion.tipo)
        anterior = observaciones_por_clave.get(clave_observacion)
        if anterior is None or observacion.fecha_observacion >= anterior.fecha_observacion:
            observaciones_por_clave[clave_observacion] = observacion
    filas = []
    for simulacion in simulaciones:
        inclusion = simulacion.get("inclusion")
        actuales = [
            item for item in items
            if item.vigente
            and item.lista_precio_id == simulacion["regla_canal"].lista_precio_id
            and inclusion is not None
            and item.catalogo_producto_id == inclusion.id
        ]
        item = max(actuales, key=lambda x: x.numero_version) if actuales else None
        promocion = promociones_por_clave.get((simulacion["regla_canal"].lista_precio_id, inclusion.id if inclusion else None))
        activa = promocion if promocion is not None and promocion.estado_observado == "activa" else None
        precio_base = item.precio_final_centavos if item else None
        clave_base = (simulacion["regla_canal"].lista_precio_id, inclusion.id if inclusion else None)
        precio_observado = observaciones_por_clave.get((*clave_base, "precio"))
        precio_efectivo = activa.precio_promocional_centavos if activa else precio_observado.precio_publicado_centavos if precio_observado else precio_base
        fila = evaluar_control(
            simulacion, precio_efectivo,
            "promocion_observada" if activa else "precio_importado" if precio_observado else "lista_interna" if item else None,
            promocion=activa, precio_base_centavos=precio_base,
        )
        cargo_observado = observaciones_por_clave.get((*clave_base, "cargo"))
        envio_observado = observaciones_por_clave.get((*clave_base, "envio"))
        desvios = []
        if cargo_observado and Decimal(str(cargo_observado.comision_pct)) != Decimal(str(simulacion["regla_canal"].comision_pct)): desvios.append("comision_observada_distinta")
        if cargo_observado and fila["actual"] and cargo_observado.cargo_fijo_centavos != fila["actual"]["cargo_fijo_centavos"]: desvios.append("cargo_fijo_observado_distinto")
        if envio_observado and fila["actual"] and envio_observado.costo_envio_centavos != fila["actual"]["envio_centavos"]: desvios.append("envio_observado_distinto")
        fila["observacion_precio"] = precio_observado; fila["observacion_cargo"] = cargo_observado
        fila["observacion_envio"] = envio_observado; fila["desvios_observados"] = desvios
        filas.append(fila)
    resumen = {"total": len(filas), "rentable": 0, "al_limite": 0, "debajo_del_piso": 0, "sin_precio": 0}
    for fila in filas: resumen[fila["estado_control"]] += 1
    return filas, resumen


def exportar_bandeja_excel(filas):
    libro = Workbook(); hoja = libro.active; hoja.title = "Control comercial"
    hoja.append(["SKU", "LISTA_CANAL", "ESTADO", "FUENTE_PRECIO", "PRECIO_BASE", "PRECIO_EFECTIVO", "PRECIO_MINIMO", "PRECIO_PROPUESTO", "LIQUIDACION_ACTUAL", "PISO_MINIMO", "DIFERENCIA", "DIFERENCIA_PCT", "PROMOCION_ACTIVA", "ACCION_RECOMENDADA", "CAMBIA_CARGO", "CAMBIA_ENVIO", "DESVIOS_OBSERVADOS"])
    for fila in filas:
        actual = fila["actual"]
        hoja.append([
            fila["costo"].producto.sku, fila["regla_canal"].lista_precio.nombre,
            fila["estado_control"], fila["fuente_precio"],
            fila["precio_base_centavos"] / 100 if fila["precio_base_centavos"] is not None else None,
            actual["precio_final_centavos"] / 100 if actual else None,
            fila["minimo"]["precio_final_centavos"] / 100,
            fila["propuesto"]["precio_final_centavos"] / 100,
            actual["liquidacion_centavos"] / 100 if actual else None,
            fila["minimo"]["piso_liquidacion_centavos"] / 100,
            fila["diferencia_precio_centavos"] / 100 if fila["diferencia_precio_centavos"] is not None else None,
            fila["diferencia_pct"], "SI" if fila["promocion_activa"] else "NO",
            fila["accion_recomendada"], "SI" if fila["cambia_cargo"] else "NO",
            "SI" if fila["cambia_envio"] else "NO",
            ", ".join(fila.get("desvios_observados", [])),
        ])
    hoja.freeze_panes = "A2"
    salida = BytesIO(); libro.save(salida); salida.seek(0); return salida
