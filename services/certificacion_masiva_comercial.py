"""Certifica escenarios comerciales desde archivos, en memoria y sin canales."""

from decimal import Decimal, InvalidOperation
from io import BytesIO

from openpyxl import Workbook

from services.importacion_productos_costeo import normalizar
from services.simulador_integral_comercial import ESCENARIOS, simular_escenario


CAMPOS = {
    "codigo": ("Codigo escenario", {"codigo", "escenario", "codigo escenario"}),
    "costo": ("Costo", {"costo", "costo unitario"}),
    "impuesto_pct": ("Impuesto %", {"impuesto", "impuesto %", "impuestos"}),
    "utilidad_pct": ("Utilidad %", {"utilidad", "utilidad %", "margen requerido"}),
    "precio_final": ("Precio final", {"precio", "precio final", "precio observado"}),
    "comision_pct": ("Comision %", {"comision", "comision %"}),
    "cargo_fijo": ("Cargo fijo", {"cargo fijo", "cargo por unidad"}),
    "umbral_envio": ("Umbral envio", {"umbral", "umbral envio"}),
    "envio": ("Costo envio", {"envio", "costo envio"}),
    "promocion_activa": ("Promocion activa", {"promocion", "promocion activa"}),
    "descuento_pct": ("Descuento %", {"descuento", "descuento %"}),
    "liquidacion_real": ("Liquidacion observada", {"liquidacion", "liquidacion real", "liquidacion observada"}),
    "estado_venta": ("Estado venta", {"estado", "estado venta"}),
}


def campos_certificacion():
    return {
        clave: {"nombre": nombre, "alias": set(alias) | {normalizar(nombre)}, "obligatorio": True}
        for clave, (nombre, alias) in CAMPOS.items()
    }


def sugerir_mapeo(encabezados):
    definiciones = campos_certificacion(); resultado = {}; usados = set()
    for indice, encabezado in enumerate(encabezados):
        limpio = normalizar(encabezado); destino = ""
        for clave, definicion in definiciones.items():
            if clave not in usados and limpio in definicion["alias"]:
                destino = clave; usados.add(clave); break
        resultado[str(indice)] = destino
    return resultado


def validar_mapeo(mapeo):
    destinos = [campo for campo in mapeo.values() if campo]
    faltantes = [d["nombre"] for clave, d in campos_certificacion().items() if d["obligatorio"] and clave not in destinos]
    if len(destinos) != len(set(destinos)): raise ValueError("Una columna fue asignada mas de una vez.")
    if faltantes: raise ValueError("Faltan columnas obligatorias: " + ", ".join(faltantes) + ".")


def _decimal(valor, nombre):
    texto = str("" if valor is None else valor).strip().replace(" ", "")
    if "," in texto and "." in texto: texto = texto.replace(".", "").replace(",", ".")
    else: texto = texto.replace(",", ".")
    try: numero = Decimal(texto)
    except InvalidOperation as error: raise ValueError(f"{nombre} no es valido") from error
    if not numero.is_finite() or numero < 0: raise ValueError(f"{nombre} no puede ser negativo")
    return numero


def _centavos(valor, nombre):
    return int((_decimal(valor, nombre) * 100).quantize(Decimal("1")))


def _booleano(valor):
    limpio = normalizar(valor)
    if limpio in {"si", "1", "true", "verdadero"}: return True
    if limpio in {"no", "0", "false", "falso"}: return False
    raise ValueError("Promocion activa debe ser SI o NO")


def _extraer(fila, mapeo):
    return {campo: fila["valores"][int(i)] if int(i) < len(fila["valores"]) else "" for i, campo in mapeo.items() if campo}


def certificar_filas(filas, mapeo):
    validar_mapeo(mapeo); salida = []
    for fila in filas:
        datos = _extraer(fila, mapeo); codigo = str(datos.get("codigo") or "").strip(); errores = []
        try:
            if not codigo: raise ValueError("Falta el codigo del escenario")
            entrada = {
                "nombre": codigo,
                "costo_centavos": _centavos(datos["costo"], "Costo"),
                "impuesto_pct": _decimal(datos["impuesto_pct"], "Impuesto"),
                "utilidad_pct": _decimal(datos["utilidad_pct"], "Utilidad"),
                "precio_final_centavos": _centavos(datos["precio_final"], "Precio final"),
                "comision_pct": _decimal(datos["comision_pct"], "Comision"),
                "cargo_fijo_centavos": _centavos(datos["cargo_fijo"], "Cargo fijo"),
                "umbral_envio_centavos": _centavos(datos["umbral_envio"], "Umbral envio"),
                "envio_centavos": _centavos(datos["envio"], "Costo envio"),
                "promocion_activa": _booleano(datos["promocion_activa"]),
                "descuento_pct": _decimal(datos["descuento_pct"], "Descuento"),
                "liquidacion_real_centavos": _centavos(datos["liquidacion_real"], "Liquidacion observada"),
                "estado_venta": str(datos["estado_venta"] or "").strip().lower(),
                "redondeo_centavos": 100,
            }
            resultado = simular_escenario(entrada)
            cierre_normal = resultado["estado_conciliacion"] in {"conciliada", "anulada", "devuelta"}
            apto = resultado["cumple_piso"] and cierre_normal
            estado = "apto" if apto else "no_apto"
        except (ValueError, KeyError) as error:
            resultado = None; estado = "error"; errores.append(str(error))
        salida.append({"numero": fila["numero"], "codigo": codigo, "estado": estado, "errores": errores, "resultado": resultado})
    return salida


def resumir_certificacion(filas):
    resumen = {"total": len(filas), "aptos": 0, "no_aptos": 0, "errores": 0, "cancelar_promocion": 0, "bajo_piso": 0}
    for fila in filas:
        if fila["estado"] == "apto": resumen["aptos"] += 1
        elif fila["estado"] == "no_apto": resumen["no_aptos"] += 1
        else: resumen["errores"] += 1
        resultado = fila.get("resultado")
        if resultado and not resultado["cumple_piso"]: resumen["bajo_piso"] += 1
        if resultado and resultado["accion_propuesta"] == "cancelar_promocion_y_actualizar_precio": resumen["cancelar_promocion"] += 1
    resumen["certificacion"] = "apta" if resumen["total"] > 0 and resumen["no_aptos"] == 0 and resumen["errores"] == 0 else "no_apta"
    return resumen


def exportar_resultados(filas):
    libro = Workbook(); hoja = libro.active; hoja.title = "Certificacion"
    hoja.append(["FILA", "CODIGO", "RESULTADO", "CUMPLE PISO", "ESTADO CONCILIACION", "ACCION PROPUESTA", "PISO", "PRECIO ACTUAL", "PRECIO MINIMO", "LIQUIDACION ESPERADA", "LIQUIDACION OBSERVADA", "DIFERENCIA", "ERRORES"])
    for fila in filas:
        r = fila.get("resultado")
        hoja.append([fila["numero"], fila["codigo"], fila["estado"], r["cumple_piso"] if r else None, r["estado_conciliacion"] if r else None, r["accion_propuesta"] if r else None, r["piso"]["piso_liquidacion_centavos"] / 100 if r else None, r["liquidacion_actual"]["precio_final_centavos"] / 100 if r else None, r["precio_minimo"]["precio_final_centavos"] / 100 if r else None, r["liquidacion_actual"]["liquidacion_centavos"] / 100 if r else None, r["entrada"]["liquidacion_real_centavos"] / 100 if r else None, r["diferencia_liquidacion_centavos"] / 100 if r else None, ", ".join(fila["errores"])])
    hoja.freeze_panes = "A2"; salida = BytesIO(); libro.save(salida); salida.seek(0); return salida


def plantilla_certificacion():
    libro = Workbook(); hoja = libro.active; hoja.title = "Escenarios"
    campos = campos_certificacion(); hoja.append([d["nombre"].upper() for d in campos.values()])
    for clave, escenario in ESCENARIOS.items():
        valores = {"codigo": clave, "costo": escenario["costo_centavos"] / 100, "impuesto_pct": escenario["impuesto_pct"], "utilidad_pct": escenario["utilidad_pct"], "precio_final": escenario["precio_final_centavos"] / 100, "comision_pct": escenario["comision_pct"], "cargo_fijo": escenario["cargo_fijo_centavos"] / 100, "umbral_envio": escenario["umbral_envio_centavos"] / 100, "envio": escenario["envio_centavos"] / 100, "promocion_activa": "SI" if escenario["promocion_activa"] else "NO", "descuento_pct": escenario["descuento_pct"], "liquidacion_real": escenario["liquidacion_real_centavos"] / 100, "estado_venta": escenario["estado_venta"]}
        hoja.append([valores[campo] for campo in campos])
    salida = BytesIO(); libro.save(salida); salida.seek(0); return salida
