"""Auditoria de solo lectura para consolidar el circuito comercial interno."""

import json
from io import BytesIO
from types import SimpleNamespace

from openpyxl import Workbook

from services.adaptadores_offline_canales import adaptar_fixture
from services.orquestador_offline_eventos import orquestar_eventos
from services.simulador_integral_comercial import escenario_predefinido, simular_escenario


def _duplicados(filas, campos):
    vistos = set(); repetidos = set()
    for fila in filas:
        clave = tuple(getattr(fila, campo, None) for campo in campos)
        if clave in vistos: repetidos.add(clave)
        vistos.add(clave)
    return len(repetidos)


def probar_circuito_sintetico():
    venta = adaptar_fixture("mercado_libre", "venta", {"id": "VENTA-DEMO", "status": "paid", "paid_amount": 1000, "order_items": [{"item": {"id": "PUB-DEMO", "seller_sku": "SKU-DEMO"}, "quantity": 1, "unit_price": 1000}]}, cuenta_codigo="DEMO-ML")[0]
    pago = adaptar_fixture("mercado_pago", "pago", {"id": "PAGO-DEMO", "external_reference": "VENTA-DEMO", "transaction_amount": 1000, "net_received_amount": 850, "fee_details": [{"amount": 150}], "status": "approved"}, cuenta_codigo="DEMO-MP")[0]
    eventos = []
    for indice, normalizado in enumerate((venta, pago), 1):
        sobre = {"version_esquema": 1, "tipo": normalizado["tipo"], "referencia": normalizado["referencia"], "datos": normalizado["datos"]}
        eventos.append(SimpleNamespace(id=indice, canal=normalizado["canal"], cuenta_codigo=normalizado["cuenta_codigo"], estado="validado", payload_json=json.dumps(sobre)))
    orquestacion = orquestar_eventos(eventos)
    promocion = simular_escenario(escenario_predefinido("promocion"))
    return {"adaptacion": len(eventos) == 2, "correlacion": orquestacion["resumen"]["cadenas_completas"] == 1, "bloqueo_escrituras": orquestacion["escrituras_dominio"] == 0 and orquestacion["acciones_externas"] == 0, "proteccion_piso": not promocion["cumple_piso"], "proteccion_promocion": promocion["accion_propuesta"] == "cancelar_promocion_y_actualizar_precio"}


def construir_auditoria(*, controles, eventos, ventas, movimientos, gestiones,
                        costos_vigentes, reglas_economicas, reglas_canal,
                        validaciones, identidades):
    hallazgos = []
    def agregar(codigo, nivel, cumple, detalle): hallazgos.append({"codigo": codigo, "nivel": nivel if not cumple else "ok", "cumple": cumple, "detalle": detalle})
    agregar("costos_vigentes", "critico", costos_vigentes > 0, f"{costos_vigentes} costos vigentes")
    agregar("reglas_economicas", "critico", reglas_economicas > 0, f"{reglas_economicas} reglas economicas vigentes")
    agregar("reglas_canal", "critico", reglas_canal > 0, f"{reglas_canal} reglas de canal vigentes")
    agregar("validaciones", "critico", validaciones > 0, f"{validaciones} reglas de validacion vigentes")
    agregar("identidades", "advertencia", identidades > 0, f"{identidades} identidades preparadas")
    externos = [c for c in controles if c.recepcion_externa_habilitada or c.acciones_externas_habilitadas]
    agregar("bloqueos_externos", "critico", not externos, f"{len(externos)} controles con flags externos")
    controles_ids = {c.id for c in controles}; huerfanos = [e for e in eventos if e.control_id not in controles_ids]
    agregar("eventos_huerfanos", "critico", not huerfanos, f"{len(huerfanos)} eventos sin control de la unidad")
    agregar("duplicados_staging", "critico", _duplicados(eventos, ("canal", "cuenta_codigo", "tipo_evento", "referencia_evento")) == 0, "Identidad idempotente de staging")
    agregar("duplicados_ventas", "critico", _duplicados(ventas, ("cuenta_codigo", "referencia_venta", "referencia_item")) == 0, "Identidad unica de ventas")
    agregar("duplicados_movimientos", "critico", _duplicados(movimientos, ("cuenta_codigo", "referencia_movimiento")) == 0, "Identidad unica de movimientos")
    certificadas = sum(bool(c.certificacion_interna_aprobada) for c in controles)
    agregar("cuentas_certificadas", "advertencia", bool(controles) and certificadas == len(controles), f"{certificadas} de {len(controles)} cuentas certificadas")
    prueba = probar_circuito_sintetico()
    for clave, cumple in prueba.items(): agregar(f"circuito_{clave}", "critico", cumple, "Ensayo sintetico interno")
    criticos = [h for h in hallazgos if not h["cumple"] and h["nivel"] == "critico"]
    advertencias = [h for h in hallazgos if not h["cumple"] and h["nivel"] == "advertencia"]
    return {"hallazgos": hallazgos, "criticos": len(criticos), "advertencias": len(advertencias), "apto_consolidacion": not criticos, "conexion_real_habilitada": False, "totales": {"controles": len(controles), "eventos": len(eventos), "ventas": len(ventas), "movimientos": len(movimientos), "gestiones": len(gestiones)}}


def exportar_auditoria(resultado):
    libro = Workbook(); hoja = libro.active; hoja.title = "Auditoria"
    hoja.append(["CODIGO", "RESULTADO", "NIVEL", "DETALLE"])
    for h in resultado["hallazgos"]: hoja.append([h["codigo"], "OK" if h["cumple"] else "PENDIENTE", h["nivel"], h["detalle"]])
    hoja.freeze_panes = "A2"; salida = BytesIO(); libro.save(salida); salida.seek(0); return salida
