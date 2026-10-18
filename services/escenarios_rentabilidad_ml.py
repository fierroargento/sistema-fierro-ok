"""Ejemplos reproducibles; nunca representan ventas o cuentas reales."""

from copy import deepcopy
from types import SimpleNamespace as Obj

from services.motor_comercial_canal import calcular_precio_minimo_canal, liquidar_precio
from services.reglas_economicas import calcular_piso_economico
from services.rentabilidad_ml_offline import CONCEPTOS, _repartir


ESCENARIOS = {
    "simple": ("Venta simple", "Costo histórico, embalaje y cargos completos."),
    "pack": ("Pack de cuatro órdenes", "SKU repetido, precios distintos y un envío compartido."),
    "neto": ("Neto y cargos repetidos", "Dos fuentes de una comisión; se descuenta una sola vez."),
    "faltantes": ("Gastos pendientes", "Publicidad sin evidencia: el resultado queda parcial."),
    "sin_costo": ("Falta costo histórico", "El resultado no se calcula usando cero o el costo actual."),
    "mayorista": ("Venta B2B simulada", "Precio efectivo ya aplicado; no configura tramos en ML."),
    "devolucion": ("Devolución parcial", "Reintegro observado sin reponer stock ni recuperar costo automáticamente."),
}
CUENTA_ENSAYO = "demo-rentabilidad-sin-conexion"
FECHA = "2026-10-20T08:00:00-03:00"
CORTE = "2026-10-21T18:00:00-03:00"


def escenario_rentabilidad(clave, *, organizacion_id, unidad_negocio_id):
    if clave not in ESCENARIOS:
        raise ValueError("Elegí uno de los ejemplos disponibles.")
    filas = [("DEMO-ORD-1", "DEMO-SKU-A", 1, 1000000)]
    envio = 100000
    if clave == "pack":
        filas = [("DEMO-ORD-1", "DEMO-SKU-A", 1, 1000000),
                 ("DEMO-ORD-2", "DEMO-SKU-B", 2, 1200000),
                 ("DEMO-ORD-3", "DEMO-SKU-A", 1, 900000),
                 ("DEMO-ORD-4", "DEMO-SKU-C", 1, 1100000)]
        envio = 400000
    elif clave == "mayorista":
        # Ejemplo compuesto: 10% promocional y luego 5% por cantidad.
        filas = [("DEMO-ORD-B2B", "DEMO-SKU-A", 5, 855000)]
        envio = 200000
    lineas = []
    eventos = []
    for pos, (order, sku, cantidad, precio) in enumerate(filas, 1):
        ident = f"linea-{pos}"
        liquidacion = liquidar_precio(precio, comision_pct=15)
        lineas.append({"linea_id": ident, "order_id": order, "referencia_linea": "1",
            "publicacion_id": f"DEMO-PUB-{pos}", "variante_id": "", "sku": sku,
            "cantidad": cantidad, "precio_unitario_centavos": precio, "fecha_venta": FECHA,
            "costo_snapshot": {"version": "DEMO-COSTO-V1", "origen_costo": "calculado_historico",
                "fuente": "Ficha de costo sintética congelada", "unitario_centavos": 400000,
                "vigente_desde": "2026-10-01T00:00:00-03:00", "incluye_embalaje": False},
            "previsto": {"fuente": "motor_comercial_canal.liquidar_precio · política sintética 15%",
                "liquidacion_centavos": liquidacion["liquidacion_centavos"] * cantidad}})
        eventos.append(_evento(f"comision-{pos}", "comision", liquidacion["comision_centavos"] * cantidad, [ident]))
    ids = [x["linea_id"] for x in lineas]
    pesos = {x["linea_id"]: x["cantidad"] * x["precio_unitario_centavos"] for x in lineas}
    reparto = _repartir(envio, ids, pesos)
    for x in lineas:
        x["previsto"]["liquidacion_centavos"] -= reparto[x["linea_id"]]
    embalaje = sum(x["cantidad"] for x in lineas) * 30000
    eventos.extend([_evento("envio-unico", "envio", envio, ids),
                    _evento("embalaje", "embalaje", embalaje, ids, impacta=False, incluido=False)])
    neto = sum(x["previsto"]["liquidacion_centavos"] for x in lineas)
    eventos.append(_evento("neto", "liquidacion_neta", neto, ids, direccion="credito", incluido=False))
    cobertura = {c: {"estado": "no_aplica", "referencia": "Ejemplo sintético: concepto no aplicable"} for c in CONCEPTOS}
    for c in ("comision", "envio", "embalaje"):
        cobertura[c] = {"estado": "confirmado", "referencia": f"Hecho sintético: {c}"}
    documento = {"version": 1, "organizacion_id": organizacion_id, "unidad_negocio_id": unidad_negocio_id,
        "cuenta_codigo": CUENTA_ENSAYO, "moneda": "ARS", "referencia_venta": f"DEMO-{clave.upper()}",
        "origen": "sintetico", "fecha_corte": CORTE, "lineas": lineas, "eventos": eventos,
        "cobertura": cobertura, "gastos_locales_previstos_centavos": embalaje}
    if clave == "neto":
        duplicado = deepcopy(eventos[0]); duplicado["fuente"] = "Otra fuente del mismo hecho sintético"
        eventos.append(duplicado)
    if clave == "faltantes":
        cobertura["publicidad"] = {"estado": "pendiente"}
    if clave == "sin_costo":
        lineas[0]["costo_snapshot"] = None
    if clave == "mayorista":
        cobertura["descuentos"] = {"estado": "confirmado",
            "referencia": "Precio efectivo sintético: promoción 10% y descuento por cantidad 5% ya aplicados"}
    if clave == "devolucion":
        documento["estado_venta"] = "devolucion_parcial"
        eventos.append(_evento("reintegro-parcial", "devoluciones", 250000, ids, incluido=False))
        cobertura["devoluciones"] = {"estado": "confirmado", "referencia": "Reintegro sintético parcial; costo sin recuperación"}
    objetivo = None
    if clave in {"simple", "neto"}:
        regla = Obj(comision_pct=15, tramos=[], umbral_envio_centavos=1,
            costo_envio_default_centavos=100000, incremento_redondeo_centavos=100)
        piso = calcular_piso_economico(430000, utilidad_pct=20, metodo_utilidad="sobre_costo",
            impuesto_pct=0, metodo_impuesto="sobre_costo", redondeo_centavos=1)
        objetivo = calcular_precio_minimo_canal(piso["piso_liquidacion_centavos"], regla)["precio_final_centavos"]
    return documento, {"nombre": ESCENARIOS[clave][0], "descripcion": ESCENARIOS[clave][1],
        "precio_objetivo_centavos": objetivo,
        "criterio_objetivo": "Recargo objetivo del 20% sobre costo de producto y embalaje; cargo de canal y envío previstos. Sin impuestos/publicidad aplicables en este ejemplo.",
        "contexto": "B2B sintético" if clave == "mayorista" else "Ejemplo sintético"}


def _evento(ident, tipo, importe, lineas, *, direccion="debito", impacta=True, incluido=True):
    return {"hecho_id": ident, "tipo": tipo, "importe_centavos": importe, "direccion": direccion,
        "lineas": list(lineas), "fuente": "Documento de ensayo sin conexión", "fecha": CORTE,
        "estado": "observado" if importe else "cero_confirmado", "impacta_saldo": impacta,
        "incluido_en_neto": incluido}
