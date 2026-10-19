"""Puente de solo lectura entre el precio interno y el analizador offline.

La fotografía conserva fuentes y previsión; los hechos del ensayo son sintéticos.
Una huella detecta cambios accidentales: no autentica un archivo externo.
"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from types import SimpleNamespace

from services.fechas import ahora_utc_naive
from services.enlace_economico_producto import _validar_tramos
from services.motor_comercial_canal import calcular_precio_minimo_canal, liquidar_precio
from services.reglas_economicas import calcular_pisos_regla


FORMATO = "venta_prueba_desde_precio_v1"
CUENTA = "demo-rentabilidad-sin-conexion"
CASOS = {"previsto": "Gastos según lo previsto", "envio_mayor": "Envío $500 más caro"}
CONCEPTOS_CANAL = ("comision", "cargo_fijo", "envio", "publicidad", "financiacion", "devoluciones")


def _huella(datos):
    return sha256(json.dumps(datos, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _fecha(valor):
    fecha = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    return fecha.replace(tzinfo=timezone.utc) if fecha.tzinfo is None else fecha.astimezone(timezone.utc)


def _centavos(valor):
    if type(valor) is not int or not 0 <= valor <= 10**15:
        raise ValueError("El enlace contiene importes no válidos.")
    return valor


def _liquidacion(traza, precio):
    politica = SimpleNamespace(**traza["politica_canal"])
    if not isinstance(traza["tramos"], list) or not 1 <= len(traza["tramos"]) <= 200:
        raise ValueError("El ensayo requiere entre 1 y 200 tramos de cargo explícitos.")
    politica.tramos = [SimpleNamespace(**t) for t in traza["tramos"]]
    _validar_tramos(politica)
    if any(getattr(politica, campo) is None for campo in
            ("comision_pct", "publicidad_pct", "financiacion_pct", "devoluciones_pct")):
        raise ValueError("La fotografía requiere tasas explícitas; un faltante no es cero.")
    _centavos(politica.umbral_envio_centavos)
    _centavos(politica.costo_envio_default_centavos)
    if _centavos(politica.incremento_redondeo_centavos) == 0:
        raise ValueError("El paso de precio debe ser mayor que cero.")
    calculo = liquidar_precio(precio, comision_pct=politica.comision_pct,
        publicidad_pct=politica.publicidad_pct, financiacion_pct=politica.financiacion_pct,
        devoluciones_pct=politica.devoluciones_pct, tramos=politica.tramos,
        umbral_envio_centavos=politica.umbral_envio_centavos,
        costo_envio_centavos=politica.costo_envio_default_centavos)
    return politica, calculo


def preparar_venta_prueba(fila, *, caso="previsto", ahora=None):
    """Una unidad; no multiplica envíos compartidos ni simula precios mayoristas."""
    if caso not in CASOS:
        raise ValueError("Elegí un caso de venta de prueba disponible.")
    traza = deepcopy(fila["trazabilidad_economica"])
    if traza.get("cobertura_estado") != "declarada_vigente":
        raise ValueError("Guardá y revisá el embalaje antes de preparar la venta de prueba.")
    if traza.get("habilita_publicacion") is not False:
        raise ValueError("El ensayo requiere un cálculo interno sin publicación habilitada.")
    fecha = _fecha((ahora or ahora_utc_naive()).isoformat()).isoformat()
    minimo = traza["minimo"]
    precio = minimo["precio_final_centavos"]
    extra = traza["embalaje_adicional_centavos"]
    _, canal = _liquidacion(traza, precio)
    enlace = {"formato": FORMATO, "fecha_snapshot": fecha, "traza": traza,
        "cantidad": 1, "cuenta_ensayo": CUENTA,
        "liquidacion_canal_prevista_centavos": canal["liquidacion_centavos"],
        "gastos_locales_previstos_centavos": extra,
        "neto_minimo_centavos": minimo["piso_liquidacion_centavos"]}
    enlace["huella_snapshot"] = _huella(enlace)
    identidad = traza["identidad_publicacion"]
    incluido = traza["evidencia_embalaje"]["modo_embalaje"] == "incluido"
    referencia = f"ENSAYO-PRECIO-{traza['catalogo_producto_id']}-{traza['politica_canal']['lista_precio_id']}"
    linea = {"linea_id": "ensayo-1", "order_id": referencia, "referencia_linea": "1",
        "sku": traza["sku"], "publicacion_id": identidad["publicacion"],
        "variante_id": identidad["variante"], "cantidad": 1,
        "precio_unitario_centavos": precio, "fecha_venta": fecha,
        "costo_snapshot": {"version": f"COSTO-{traza['costo']['id']}-V{traza['costo']['numero_version']}",
            "origen_costo": "calculado_historico", "fuente": f"Snapshot de ensayo {enlace['huella_snapshot']}",
            "unitario_centavos": traza["costo"]["costo_total_centavos"],
            "vigente_desde": _fecha(traza["costo"]["vigente_desde"]).isoformat(),
            "vigente_hasta": _fecha(traza["costo"]["vigente_hasta"]).isoformat() if traza["costo"]["vigente_hasta"] else None,
            "incluye_embalaje": incluido},
        "previsto": {"fuente": f"Cálculo congelado {enlace['huella_snapshot']}",
            "liquidacion_centavos": canal["liquidacion_centavos"]}}
    aumento_envio = 50000 if caso == "envio_mayor" else 0
    if canal["liquidacion_centavos"] < aumento_envio:
        raise ValueError("El ejemplo de envío adicional supera la liquidación prevista; usá el caso según lo previsto.")
    eventos = []
    cobertura = {}

    def agregar(concepto, importe, *, local=False):
        cobertura[concepto] = {"estado": "confirmado", "referencia": "Hecho sintético del ensayo"}
        eventos.append({"hecho_id": f"ensayo-{concepto}", "tipo": concepto,
            "importe_centavos": importe, "direccion": "debito", "lineas": ["ensayo-1"],
            "fuente": "Hecho sintético; no proviene de ML/MP", "fecha": fecha,
            "estado": "observado" if importe else "cero_confirmado",
            "impacta_saldo": not local, "incluido_en_neto": not local})

    for concepto in CONCEPTOS_CANAL:
        importe = canal[concepto + "_centavos"] + (aumento_envio if concepto == "envio" else 0)
        agregar(concepto, importe)
    if incluido:
        cobertura["embalaje"] = {"estado": "confirmado", "referencia": "Incluido en las líneas declaradas del costo congelado"}
    else:
        agregar("embalaje", extra, local=True)
    cobertura["descuentos"] = {"estado": "no_aplica", "referencia": "Ensayo al precio mínimo sin descuento adicional"}
    # La política comercial no aporta comprobantes impositivos de una venta.
    cobertura["impuestos"] = {"estado": "pendiente"}
    eventos.append({"hecho_id": "ensayo-neto", "tipo": "liquidacion_neta",
        "importe_centavos": canal["liquidacion_centavos"] - aumento_envio,
        "direccion": "credito", "lineas": ["ensayo-1"],
        "fuente": "Cobro sintético del ensayo; no es un saldo MP", "fecha": fecha,
        "estado": "observado", "impacta_saldo": True, "incluido_en_neto": False})
    return {"version": 1, "organizacion_id": traza["organizacion_id"],
        "unidad_negocio_id": traza["unidad_negocio_id"], "cuenta_codigo": CUENTA,
        "moneda": "ARS", "referencia_venta": referencia, "origen": "sintetico",
        "fecha_corte": fecha, "lineas": [linea], "eventos": eventos,
        "cobertura": cobertura, "gastos_locales_previstos_centavos": extra,
        "enlace_precio": enlace, "caso_enlace": caso,
        "pendientes_fuente": ["Cuenta y publicación declaradas; sin autenticación externa",
            "Venta y cobro sintéticos; no son movimientos operativos"]}


def evaluar_enlace_venta(documento, resultado):
    """Verifica la fotografía y compara usando el resultado del motor existente.

No consulta el costo actual: releer el archivo debe conservar su historia.
Solo admite el ensayo sintético de una unidad, no certifica una venta real.
"""
    e = documento.get("enlace_precio")
    try:
        if not isinstance(e, dict) or e.get("formato") != FORMATO:
            raise ValueError("Formato de enlace de precio no válido.")
        if _huella({k: v for k, v in e.items() if k != "huella_snapshot"}) != e.get("huella_snapshot"):
            raise ValueError("Cambió la fotografía de precio; no coincide su huella.")
        t = e["traza"]
        if _huella({k: v for k, v in t.items() if k != "huella_enlace"}) != t.get("huella_enlace"):
            raise ValueError("Cambió la trazabilidad económica del cálculo.")
        if (documento["organizacion_id"], documento["unidad_negocio_id"], documento["moneda"]) != (t["organizacion_id"], t["unidad_negocio_id"], t["moneda"]):
            raise ValueError("El cálculo congelado pertenece a otro contexto.")
        if (documento["origen"] != "sintetico" or documento["cuenta_codigo"] != CUENTA
                or e["cuenta_ensayo"] != CUENTA or t.get("habilita_publicacion") is not False
                or t.get("cobertura_estado") != "declarada_vigente"):
            raise ValueError("El enlace solo admite ensayos sintéticos con embalaje revisado.")
        if len(documento["lineas"]) != 1 or type(e["cantidad"]) is not int or e["cantidad"] != 1:
            raise ValueError("El enlace de prueba requiere una única unidad.")
        x = documento["lineas"][0]
        identidad = t["identidad_publicacion"]
        if (x["sku"], x["publicacion_id"], x.get("variante_id", ""), x["cantidad"]) != (t["sku"], identidad["publicacion"], identidad["variante"], 1):
            raise ValueError("La venta no corresponde al SKU, publicación o variante del cálculo.")
        congelado = _fecha(e["fecha_snapshot"])
        if congelado > _fecha(x["fecha_venta"]):
            raise ValueError("No se aplica un costo actual a una venta anterior al snapshot.")
        for origen in (t["costo"], t["regla_economica"], t["politica_canal"]):
            if _fecha(origen["vigente_desde"]) > congelado or (origen["vigente_hasta"] and congelado >= _fecha(origen["vigente_hasta"])):
                raise ValueError("Las fuentes no estaban vigentes al congelar el cálculo.")
        costo = x["costo_snapshot"]
        if (costo["unitario_centavos"] != t["costo"]["costo_total_centavos"]
                or costo["version"] != f"COSTO-{t['costo']['id']}-V{t['costo']['numero_version']}"
                or costo["fuente"] != f"Snapshot de ensayo {e['huella_snapshot']}"
                or _fecha(costo["vigente_desde"]) != _fecha(t["costo"]["vigente_desde"])
                or (costo.get("vigente_hasta") and _fecha(costo["vigente_hasta"])) != (t["costo"]["vigente_hasta"] and _fecha(t["costo"]["vigente_hasta"]))
                or costo["incluye_embalaje"] != (t["evidencia_embalaje"]["modo_embalaje"] == "incluido")):
            raise ValueError("El costo de la venta difiere del snapshot congelado.")
        precio = _centavos(t["minimo"]["precio_final_centavos"])
        extra = _centavos(t["embalaje_adicional_centavos"])
        embalaje = t["evidencia_embalaje"]
        if (embalaje["modo_embalaje"] not in {"incluido", "adicional", "sin_costo"}
                or embalaje["embalaje_adicional_centavos"] != extra
                or (embalaje["modo_embalaje"] != "adicional" and extra)
                or (embalaje["modo_embalaje"] == "adicional" and not extra)):
            raise ValueError("La fotografía de embalaje es contradictoria.")
        politica, canal = _liquidacion(t, precio)
        piso = calcular_pisos_regla(_centavos(t["costo"]["costo_total_centavos"]), SimpleNamespace(**t["regla_economica"]))["minimo"]["piso_liquidacion_centavos"]
        primer_precio = calcular_precio_minimo_canal(piso + extra, politica)["precio_final_centavos"]
        if (precio != primer_precio or t["minimo"]["piso_liquidacion_centavos"] != piso
                or e["neto_minimo_centavos"] != piso or canal["liquidacion_centavos"] - extra != t["minimo"]["liquidacion_centavos"]
                or e["liquidacion_canal_prevista_centavos"] != canal["liquidacion_centavos"]
                or e["gastos_locales_previstos_centavos"] != extra or documento["gastos_locales_previstos_centavos"] != extra
                or x["previsto"] != {"fuente": f"Cálculo congelado {e['huella_snapshot']}", "liquidacion_centavos": canal["liquidacion_centavos"]}):
            raise ValueError("La previsión no reproduce el mínimo económico congelado.")
        neto = resultado["totales"]["ingreso_economico_centavos"] - resultado["totales"]["gastos_centavos"]
        previsto = canal["liquidacion_centavos"] - extra
        return {"huella_snapshot": e["huella_snapshot"], "fecha_snapshot": e["fecha_snapshot"],
            "costo_version_id": t["costo"]["id"], "costo_numero_version": t["costo"]["numero_version"],
            "politica_numero_version": t["politica_canal"]["numero_version"],
            "cuenta_declarada": identidad["cuenta_codigo"], "publicacion_declarada": identidad["publicacion"],
            "precio_minimo_centavos": precio, "neto_minimo_centavos": piso,
            "neto_previsto_centavos": previsto, "neto_ensayo_centavos": neto,
            "diferencia_previsto_centavos": neto - previsto, "diferencia_minimo_centavos": neto - piso,
            "estado": "bajo_minimo" if neto < piso else "cubre_minimo",
            "definitivo": False, "publicacion_habilitada": False,
            "alcance": "Comparación sintética de conceptos declarados; faltantes no equivalen a cero."}
    except (KeyError, TypeError, AttributeError, OverflowError) as error:
        raise ValueError("El enlace de precio está incompleto o no es válido.") from error
