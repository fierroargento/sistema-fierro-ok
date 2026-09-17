"""Simulacion economica integral en memoria, sin persistencia ni canales."""

from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from types import SimpleNamespace

from services.motor_comercial_canal import calcular_precio_minimo_canal, liquidar_precio
from services.reglas_economicas import calcular_piso_economico


ESCENARIOS = {
    "cargo_fijo": {
        "nombre": "Precio bajo con cargo fijo", "costo_centavos": 1800000,
        "impuesto_pct": 5, "utilidad_pct": 20, "precio_final_centavos": 2500000,
        "comision_pct": 15, "cargo_fijo_centavos": 143000,
        "umbral_envio_centavos": 3300000, "envio_centavos": 600000,
        "promocion_activa": False, "descuento_pct": 0,
        "liquidacion_real_centavos": 1982000, "estado_venta": "confirmada",
    },
    "envio": {
        "nombre": "Precio alto con envio", "costo_centavos": 2600000,
        "impuesto_pct": 5, "utilidad_pct": 25, "precio_final_centavos": 4200000,
        "comision_pct": 15, "cargo_fijo_centavos": 143000,
        "umbral_envio_centavos": 3300000, "envio_centavos": 650000,
        "promocion_activa": False, "descuento_pct": 0,
        "liquidacion_real_centavos": 2800000, "estado_venta": "confirmada",
    },
    "promocion": {
        "nombre": "Promocion retiene precio anterior", "costo_centavos": 82000,
        "impuesto_pct": 5, "utilidad_pct": 20, "precio_final_centavos": 100000,
        "comision_pct": 15, "cargo_fijo_centavos": 0,
        "umbral_envio_centavos": 3300000, "envio_centavos": 0,
        "promocion_activa": True, "descuento_pct": 9.09,
        "liquidacion_real_centavos": 85000, "estado_venta": "confirmada",
    },
    "devolucion": {
        "nombre": "Venta devuelta", "costo_centavos": 1000000,
        "impuesto_pct": 5, "utilidad_pct": 20, "precio_final_centavos": 1800000,
        "comision_pct": 15, "cargo_fijo_centavos": 143000,
        "umbral_envio_centavos": 3300000, "envio_centavos": 500000,
        "promocion_activa": False, "descuento_pct": 0,
        "liquidacion_real_centavos": 0, "estado_venta": "devuelta",
    },
}


def _porcentaje(valor, nombre):
    numero = Decimal(str(valor or 0).replace(",", "."))
    if not numero.is_finite() or numero < 0 or numero >= 100:
        raise ValueError(f"{nombre} debe estar entre 0 y menos de 100%.")
    return numero


def _regla(datos):
    umbral = int(datos["umbral_envio_centavos"])
    tramo = SimpleNamespace(
        precio_desde_centavos=0,
        precio_hasta_centavos=umbral if umbral > 0 else None,
        cargo_fijo_centavos=int(datos["cargo_fijo_centavos"]),
    )
    return SimpleNamespace(
        comision_pct=datos["comision_pct"], tramos=[tramo],
        publicidad_pct=datos.get("publicidad_pct", 0),
        financiacion_pct=datos.get("financiacion_pct", 0),
        devoluciones_pct=datos.get("devoluciones_pct", 0),
        umbral_envio_centavos=umbral,
        costo_envio_default_centavos=int(datos["envio_centavos"]),
        incremento_redondeo_centavos=max(1, int(datos.get("redondeo_centavos", 100))),
    )


def simular_escenario(datos):
    estado_venta = str(datos.get("estado_venta") or "confirmada").strip().lower()
    if estado_venta not in {"confirmada", "cancelada", "devuelta", "devolucion_parcial"}:
        raise ValueError("El estado de venta simulado no es valido.")
    costo = int(datos["costo_centavos"]); precio = int(datos["precio_final_centavos"])
    real = int(datos.get("liquidacion_real_centavos", 0))
    if min(costo, precio, real) < 0: raise ValueError("Los importes simulados no pueden ser negativos.")
    piso = calcular_piso_economico(
        costo, impuesto_pct=datos.get("impuesto_pct", 0), metodo_impuesto="sobre_costo",
        utilidad_pct=datos.get("utilidad_pct", 0), metodo_utilidad="sobre_costo",
        redondeo_centavos=max(1, int(datos.get("redondeo_centavos", 100))),
    )
    regla = _regla(datos)
    actual = liquidar_precio(
        precio, comision_pct=regla.comision_pct, tramos=regla.tramos,
        publicidad_pct=regla.publicidad_pct,
        financiacion_pct=regla.financiacion_pct,
        devoluciones_pct=regla.devoluciones_pct,
        umbral_envio_centavos=regla.umbral_envio_centavos,
        costo_envio_centavos=regla.costo_envio_default_centavos,
    )
    minimo = calcular_precio_minimo_canal(piso["piso_liquidacion_centavos"], regla)
    descuento = _porcentaje(datos.get("descuento_pct", 0), "El descuento")
    divisor = Decimal("1") - descuento / Decimal("100")
    base_promocional = int((Decimal(minimo["precio_final_centavos"]) / divisor).to_integral_value(rounding=ROUND_CEILING))
    cumple = actual["liquidacion_centavos"] >= piso["piso_liquidacion_centavos"]
    diferencia_esperada = real - actual["liquidacion_centavos"]
    tolerancia = int(datos.get("tolerancia_centavos", 1))
    if estado_venta == "cancelada": estado_conciliacion = "anulada"
    elif estado_venta == "devuelta": estado_conciliacion = "devuelta"
    elif estado_venta == "devolucion_parcial": estado_conciliacion = "devolucion_parcial"
    elif real == 0: estado_conciliacion = "pendiente"
    elif diferencia_esperada < -tolerancia: estado_conciliacion = "pago_parcial"
    elif diferencia_esperada > tolerancia: estado_conciliacion = "diferencia_a_favor"
    else: estado_conciliacion = "conciliada"
    promocion = bool(datos.get("promocion_activa"))
    if cumple: accion = "sin_accion"
    elif promocion: accion = "cancelar_promocion_y_actualizar_precio"
    else: accion = "actualizar_precio"
    pasos = [
        {"nombre": "Costo", "importe_centavos": costo, "estado": "dato"},
        {"nombre": "Piso con utilidad e impuestos", "importe_centavos": piso["piso_liquidacion_centavos"], "estado": "dato"},
        {"nombre": "Liquidacion esperada", "importe_centavos": actual["liquidacion_centavos"], "estado": "cumple" if cumple else "no_cumple"},
        {"nombre": "Liquidacion observada", "importe_centavos": real, "estado": estado_conciliacion},
    ]
    return {
        "entrada": dict(datos), "piso": piso, "liquidacion_actual": actual,
        "precio_minimo": minimo, "precio_base_con_descuento_centavos": base_promocional,
        "cumple_piso": cumple, "margen_sobre_piso_centavos": actual["liquidacion_centavos"] - piso["piso_liquidacion_centavos"],
        "diferencia_liquidacion_centavos": diferencia_esperada,
        "estado_conciliacion": estado_conciliacion, "accion_propuesta": accion,
        "pasos": pasos,
    }


def escenario_predefinido(clave):
    if clave not in ESCENARIOS: raise ValueError("El escenario solicitado no existe.")
    return dict(ESCENARIOS[clave])
