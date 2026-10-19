"""Resultado económico por línea sobre evidencia offline, sin DB ni red.

Los precios previstos llegan congelados desde el motor comercial existente.
La conciliación financiera sigue usando conciliar_venta; no es otro libro MP.
"""

from copy import deepcopy
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from types import SimpleNamespace

from services.conciliacion_liquidaciones_canal import conciliar_venta


CONCEPTOS = ("comision", "cargo_fijo", "envio", "embalaje", "publicidad",
             "financiacion", "descuentos", "devoluciones", "impuestos")
TIPOS = set(CONCEPTOS) - {"descuentos"} | {"retencion", "pago_bruto", "liquidacion_neta"}
ESTADOS = {"observado", "estimado", "asignado", "cero_confirmado"}
MAX_CENTAVOS = 10**15


def _entero(valor, nombre, *, minimo=0, maximo=MAX_CENTAVOS):
    if isinstance(valor, bool) or not isinstance(valor, int) or not minimo <= valor <= maximo:
        raise ValueError(f"{nombre}: se requiere un entero entre {minimo} y {maximo}.")
    return valor


def _texto(valor, nombre):
    if not isinstance(valor, str) or not valor.strip() or len(valor) > 200:
        raise ValueError(f"{nombre}: falta una referencia válida.")
    return valor.strip()


def _fecha(valor):
    try:
        fecha = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        if fecha.tzinfo is None:
            raise ValueError()
        return fecha
    except (ValueError, TypeError, OverflowError):
        raise ValueError("Las fechas deben incluir zona horaria.") from None


def _repartir(importe, ids, pesos):
    """Mayor resto, con desempate estable; conserva incluso el último centavo."""
    ids = sorted(ids)
    total = sum(pesos[i] for i in ids)
    pesos = {i: pesos[i] if total else 1 for i in ids}
    total = total or len(ids)
    cuotas = {i: importe * pesos[i] // total for i in ids}
    restos = sorted(ids, key=lambda i: (-(importe * pesos[i] % total), i))
    for i in restos[:importe - sum(cuotas.values())]:
        cuotas[i] += 1
    return cuotas


def analizar_rentabilidad(documento, *, organizacion_id, unidad_negocio_id, cuenta_codigo):
    """Contrato v1: una operación/pack, líneas originales y hechos normalizados.

    Evidencia original no se modifica. Dos fuentes del mismo hecho deben
    coincidir; diferencias se rechazan para revisión, nunca se suman.
    """
    d = deepcopy(documento)
    if not isinstance(d, dict) or type(d.get("version")) is not int or d["version"] != 1:
        raise ValueError("Contrato de rentabilidad no compatible.")
    for campo, esperado in (("organizacion_id", organizacion_id), ("unidad_negocio_id", unidad_negocio_id)):
        if _entero(d.get(campo), campo, minimo=1) != esperado:
            raise ValueError("La evidencia no pertenece al contexto activo.")
    if _texto(d.get("cuenta_codigo"), "Cuenta") != cuenta_codigo:
        raise ValueError("La evidencia pertenece a otra cuenta.")
    if d.get("moneda") != "ARS":
        raise ValueError("Este ensayo requiere importes ARS; no convierte monedas.")
    if d.get("origen") not in {"sintetico", "archivo_offline"}:
        raise ValueError("Origen offline no válido.")
    try:
        entrada_json = json.dumps(d, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError, RecursionError):
        raise ValueError("La evidencia contiene valores no representables.") from None
    if len(entrada_json.encode()) > 2_000_000:
        raise ValueError("La evidencia supera 2 MB.")
    referencia = _texto(d.get("referencia_venta"), "Operación")
    estado_venta = d.get("estado_venta", "confirmada")
    if estado_venta not in {"confirmada", "cancelada", "devuelta", "devolucion_parcial"}:
        raise ValueError("Estado de venta no válido.")
    corte = _fecha(d.get("fecha_corte"))
    lineas = d.get("lineas")
    if not isinstance(lineas, list) or not 1 <= len(lineas) <= 200:
        raise ValueError("El ensayo admite entre 1 y 200 líneas.")
    filas, pesos, identidades, ventas = {}, {}, set(), []
    pendientes = d.get("pendientes_fuente", [])
    if not isinstance(pendientes, list) or len(pendientes) > 200:
        raise ValueError("Pendientes de fuente no válidos.")
    faltantes = [_texto(p, "Pendiente de fuente") for p in pendientes]
    for x in lineas:
        if not isinstance(x, dict):
            raise ValueError("Línea no válida.")
        ident = _texto(x.get("linea_id"), "Línea")
        identidad = (_texto(x.get("order_id"), "Orden"), _texto(x.get("referencia_linea"), "Referencia de línea"))
        if ident in filas or identidad in identidades:
            raise ValueError("Línea original repetida.")
        identidades.add(identidad)
        for campo in ("sku", "publicacion_id"):
            _texto(x.get(campo), campo)
        cantidad = _entero(x.get("cantidad"), "Cantidad", minimo=1, maximo=10**6)
        precio = _entero(x.get("precio_unitario_centavos"), "Precio")
        bruto = _entero(precio * cantidad, "Ingreso de línea")
        fecha = _fecha(x.get("fecha_venta"))
        if fecha > corte:
            raise ValueError("La venta es posterior al corte.")
        costo = x.get("costo_snapshot")
        costo_total = None
        if costo is None:
            faltantes.append(f"Costo histórico de {ident}")
        else:
            if not isinstance(costo, dict) or costo.get("origen_costo") not in {"calculado_historico", "comprobante_historico"}:
                raise ValueError("El costo requiere tipo de origen y snapshot histórico.")
            _texto(costo.get("version"), "Versión de costo")
            _texto(costo.get("fuente"), "Fuente de costo")
            if _fecha(costo.get("vigente_desde")) > fecha or (costo.get("vigente_hasta") and fecha >= _fecha(costo["vigente_hasta"])):
                raise ValueError("La versión de costo no corresponde a la fecha de venta.")
            if not isinstance(costo.get("incluye_embalaje"), bool):
                raise ValueError("Debe indicarse si el costo incluye embalaje.")
            costo_total = _entero(_entero(costo.get("unitario_centavos"), "Costo unitario") * cantidad, "Costo de línea")
        previsto = x.get("previsto")
        if previsto is None:
            faltantes.append(f"Liquidación prevista de {ident}")
        else:
            if not isinstance(previsto, dict):
                raise ValueError("Previsión no válida.")
            _texto(previsto.get("fuente"), "Fuente de previsión")
            _entero(previsto.get("liquidacion_centavos"), "Liquidación prevista", minimo=-MAX_CENTAVOS)
        filas[ident] = {"linea_id": ident, "order_id": identidad[0], "referencia_linea": identidad[1],
                       "sku": x["sku"], "publicacion_id": x["publicacion_id"], "variante_id": x.get("variante_id", ""),
                       "cantidad": cantidad, "ingreso_centavos": bruto, "costo_centavos": costo_total,
                       "costo_snapshot": costo, "previsto": previsto, "componentes": [],
                       "ajuste_ingreso_centavos": 0, "gastos_centavos": 0}
        pesos[ident] = bruto
        ventas.append(SimpleNamespace(referencia_venta=referencia, cuenta_codigo=cuenta_codigo,
            liquidacion_esperada_centavos=previsto["liquidacion_centavos"] if previsto else 0,
            cantidad=cantidad, piso_unitario_snapshot_centavos=None, importe_bruto_centavos=bruto,
            estado=estado_venta))
    cobertura = d.get("cobertura", {})
    if not isinstance(cobertura, dict):
        raise ValueError("Cobertura no válida.")
    conceptos = []
    for concepto in CONCEPTOS:
        dato = cobertura.get(concepto, {})
        if not isinstance(dato, dict):
            raise ValueError("Cobertura no válida.")
        estado = dato.get("estado", "pendiente")
        if estado not in {"confirmado", "no_aplica", "pendiente"}:
            raise ValueError("Estado de cobertura no válido.")
        if estado != "pendiente":
            _texto(dato.get("referencia"), "Evidencia de cobertura")
        else:
            faltantes.append(concepto)
        conceptos.append({"concepto": concepto, "estado": estado, "referencia": dato.get("referencia", "")})
    eventos = d.get("eventos", [])
    if not isinstance(eventos, list) or len(eventos) > 1000:
        raise ValueError("El ensayo admite hasta 1000 hechos.")
    hechos, duplicados = {}, 0
    for e in eventos:
        if not isinstance(e, dict):
            raise ValueError("Hecho no válido.")
        clave = _texto(e.get("hecho_id"), "Hecho")
        _texto(e.get("fuente"), "Fuente del hecho")
        tipo, estado = e.get("tipo"), e.get("estado")
        if tipo not in TIPOS or estado not in ESTADOS or e.get("direccion") not in {"credito", "debito"}:
            raise ValueError("Tipo, dirección o estado del hecho no válido.")
        importe = _entero(e.get("importe_centavos"), "Importe del hecho")
        if estado == "cero_confirmado" and importe:
            raise ValueError("Cero confirmado requiere importe cero.")
        if _fecha(e.get("fecha")) > corte:
            raise ValueError("El hecho es posterior al corte.")
        ids = e.get("lineas")
        if not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids) or len(ids) != len(set(ids)) or any(i not in filas for i in ids):
            raise ValueError("El hecho debe indicar líneas propias, sin repetirlas.")
        if not isinstance(e.get("incluido_en_neto"), bool) or not isinstance(e.get("impacta_saldo"), bool):
            raise ValueError("El hecho debe declarar su relación con el saldo y el neto.")
        if tipo == "liquidacion_neta" and (estado not in {"observado", "cero_confirmado"} or e["incluido_en_neto"] or not e["impacta_saldo"]):
            raise ValueError("Liquidación neta no válida.")
        if clave in hechos:
            anterior = hechos[clave]
            if {k: v for k, v in anterior.items() if k != "fuentes"} != {k: v for k, v in e.items() if k != "fuente"}:
                raise ValueError("Fuentes incompatibles para el mismo hecho; requiere revisión.")
            anterior["fuentes"].append(e["fuente"])
            duplicados += 1
        else:
            hechos[clave] = {k: v for k, v in e.items() if k != "fuente"} | {"fuentes": [e["fuente"]]}
    lineas_con_neto = {ident for e in hechos.values() if e["tipo"] == "liquidacion_neta" for ident in e["lineas"]}
    movimientos = []
    saldo_reconstruido = sum(pesos.values())
    cobertura_hechos = {concepto: set() for concepto in CONCEPTOS}
    for e in hechos.values():
        tipo = e["tipo"]
        cubierto_por_neto = set(e["lineas"]) <= lineas_con_neto
        if e["incluido_en_neto"] and not cubierto_por_neto:
            faltantes.append(f"Neto de referencia para {e['hecho_id']}")
        if e["estado"] in {"estimado", "asignado"}:
            faltantes.append(f"Gasto no observado: {e['hecho_id']}")
        if tipo == "retencion" and e.get("tratamiento_economico") != "credito_fiscal_documentado":
            faltantes.append(f"Clasificación económica de retención: {e['hecho_id']}")
        if tipo in {"pago_bruto", "liquidacion_neta"} and e["direccion"] != "credito":
            raise ValueError("El cobro debe ser un crédito; usar devolución para un reintegro.")
        if cobertura.get(tipo, {}).get("estado") == "no_aplica" and e["importe_centavos"]:
            raise ValueError("Un concepto no aplicable no puede tener un gasto o ajuste.")
        if tipo == "embalaje" and any(filas[i]["costo_snapshot"] and filas[i]["costo_snapshot"]["incluye_embalaje"] for i in e["lineas"]):
            raise ValueError("El embalaje ya integra el costo: no puede descontarse otra vez.")
        if tipo in cobertura_hechos and e["estado"] in {"observado", "cero_confirmado"}:
            cobertura_hechos[tipo].update(e["lineas"])
        if tipo not in {"pago_bruto", "liquidacion_neta", "retencion"}:
            for ident, importe in _repartir(e["importe_centavos"], e["lineas"], pesos).items():
                firmado = importe * (1 if e["direccion"] == "debito" else -1)
                if tipo == "devoluciones":
                    filas[ident]["ajuste_ingreso_centavos"] -= firmado
                else:
                    filas[ident]["gastos_centavos"] += firmado
                filas[ident]["componentes"].append({"concepto": tipo, "importe_centavos": firmado,
                    "hecho_id": e["hecho_id"], "fuentes": e["fuentes"], "estado": e["estado"],
                    "asignacion": "proporcional_al_ingreso" if len(e["lineas"]) > 1 else "directa"})
        impacta = e["impacta_saldo"] and e["estado"] in {"observado", "cero_confirmado"}
        # El neto reemplaza el bruto y los cargos que ya contiene, no el resultado económico.
        if tipo == "pago_bruto" and set(e["lineas"]) & lineas_con_neto and not cubierto_por_neto:
            raise ValueError("El pago bruto mezcla líneas con y sin neto; separar el alcance.")
        if cubierto_por_neto and (tipo == "pago_bruto" or e["incluido_en_neto"]):
            impacta = False
        movimientos.append(SimpleNamespace(referencia_venta=referencia, cuenta_codigo=cuenta_codigo,
            referencia_movimiento=e["hecho_id"], impacta_saldo=impacta, estado="confirmado",
            importe_centavos=e["importe_centavos"], direccion=e["direccion"]))
        if tipo not in {"pago_bruto", "liquidacion_neta"} and e["impacta_saldo"]:
            saldo_reconstruido += e["importe_centavos"] * (1 if e["direccion"] == "credito" else -1)
    for concepto in CONCEPTOS:
        if concepto == "descuentos":
            continue  # El precio efectivo de línea ya los contempla; la fuente se declara en cobertura.
        if cobertura.get(concepto, {}).get("estado") == "confirmado":
            cubiertas = set(cobertura_hechos[concepto])
            if concepto == "embalaje":
                cubiertas.update(i for i, f in filas.items() if f["costo_snapshot"] and f["costo_snapshot"]["incluye_embalaje"])
            if cubiertas != set(filas):
                faltantes.append(f"Detalle incompleto de {concepto}")
    if estado_venta != "confirmada" and not cobertura_hechos["devoluciones"]:
        faltantes.append("Resolución económica de la anulación o devolución")
    hay_cobro = any(m.impacta_saldo and e["tipo"] in {"pago_bruto", "liquidacion_neta"}
                   for m, e in zip(movimientos, hechos.values()))
    if not hay_cobro:
        faltantes.append("Cobro observado")
    conciliacion = conciliar_venta(referencia, cuenta_codigo, ventas, movimientos)
    diferencia_evidencia = conciliacion["liquidacion_real_centavos"] - saldo_reconstruido if hay_cobro else None
    if diferencia_evidencia is not None and abs(diferencia_evidencia) > 1:
        faltantes.append("Diferencia entre cobro y reconstrucción del detalle")
    for fila in filas.values():
        ingreso = fila["ingreso_centavos"] + fila["ajuste_ingreso_centavos"]
        resultado = ingreso - fila["gastos_centavos"] - fila["costo_centavos"] if fila["costo_centavos"] is not None else None
        fila["ingreso_economico_centavos"] = ingreso
        fila["resultado_centavos"] = resultado
        fila["margen_pct"] = str((Decimal(resultado) * 100 / ingreso).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if resultado is not None and ingreso > 0 else None
    totales = {k: sum(f[k] for f in filas.values()) for k in ("ingreso_centavos", "ingreso_economico_centavos", "gastos_centavos")}
    costo_completo = all(f["costo_centavos"] is not None for f in filas.values())
    totales["costo_centavos"] = sum(f["costo_centavos"] for f in filas.values()) if costo_completo else None
    totales["resultado_centavos"] = sum(f["resultado_centavos"] for f in filas.values()) if costo_completo else None
    esperado = all(f["previsto"] for f in filas.values())
    gastos_previstos = d.get("gastos_locales_previstos_centavos")
    if gastos_previstos is None:
        faltantes.append("Gastos locales previstos")
        esperado = False
        gastos_previstos = 0
    else:
        gastos_previstos = _entero(gastos_previstos, "Gastos locales previstos")
    totales["resultado_previsto_centavos"] = conciliacion["liquidacion_esperada_centavos"] - gastos_previstos - totales["costo_centavos"] if esperado and costo_completo else None
    totales["diferencia_resultado_centavos"] = totales["resultado_centavos"] - totales["resultado_previsto_centavos"] if esperado and costo_completo else None
    ingreso = totales["ingreso_economico_centavos"]
    totales["margen_pct"] = str((Decimal(totales["resultado_centavos"]) * 100 / ingreso).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if costo_completo and ingreso > 0 else None
    r = {"version": 1, "organizacion_id": organizacion_id, "unidad_negocio_id": unidad_negocio_id,
         "cuenta_codigo": cuenta_codigo, "moneda": "ARS", "referencia_venta": referencia,
         "origen": d["origen"], "fecha_corte": d["fecha_corte"], "modo": "rentabilidad_ml_offline",
         "estado_venta": estado_venta,
         "huella_entrada": sha256(entrada_json.encode()).hexdigest(),
         "estado": "no_calculable" if not costo_completo else "parcial" if faltantes else "alcance_declarado_completo",
         "faltantes": sorted(set(faltantes)), "cobertura": conceptos, "lineas": list(filas.values()),
         "hechos": list(hechos.values()), "fuentes_duplicadas_no_sumadas": duplicados,
         "totales": totales, "liquidacion": {"prevista_centavos": conciliacion["liquidacion_esperada_centavos"] if esperado else None,
             "observada_centavos": conciliacion["liquidacion_real_centavos"] if hay_cobro else None,
             "reconstruida_centavos": saldo_reconstruido, "diferencia_detalle_centavos": diferencia_evidencia,
             "estado": conciliacion["estado_conciliacion"] if esperado else "sin_prevision"},
         "controles": {"persistencia": False, "conexiones_externas": 0, "stock": 0, "pagos": 0, "publicaciones": 0}}
    r["huella_rentabilidad"] = sha256(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return r
