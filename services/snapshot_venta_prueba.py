"""Paquete ML/MP ficticio para el mismo ensayo y sus fuentes congeladas.

Serializa el contrato offline que ya consume el sistema; no consulta APIs.
"""
from copy import deepcopy
from decimal import Decimal

from services.lectura_ml_rentabilidad import FORMATO_ML
from services.lectura_mp_rentabilidad import FORMATO_MP
from services.venta_prueba_precio import CUENTA

CASOS = {"completo": "Cobro y cargos coincidentes", "sin_neto": "MP sin neto informado",
         "cargo_diferente": "MP con $100 más de comisión"}


def snapshot_venta_prueba(entrada, *, caso="completo"):
    if caso not in CASOS:
        raise ValueError("Elegí un contraste MP disponible.")
    if entrada.get("origen") != "sintetico" or entrada.get("cuenta_codigo") != CUENTA or len(entrada.get("lineas", [])) != 1:
        raise ValueError("La plantilla ML/MP requiere una única línea del ensayo sintético.")
    d = deepcopy(entrada)
    x = d["lineas"][0]
    if x["cantidad"] != 1:
        raise ValueError("No se extrapolan cargos de una unidad a un pack.")
    por_tipo = {}
    for e in d["eventos"]:
        if e["tipo"] in por_tipo:
            raise ValueError("El ensayo tiene hechos ambiguos para preparar los snapshots.")
        por_tipo[e["tipo"]] = e
    if not {"comision", "envio", "liquidacion_neta"} <= por_tipo.keys():
        raise ValueError("Faltan hechos del ensayo para preparar ML/MP.")
    dinero = lambda c: format(Decimal(c) / 100, ".2f")
    seller, shipment, pago = "DEMO-SELLER-PRECIO", "DEMO-SHIP-PRECIO", "DEMO-MP-PRECIO"
    orden = x["order_id"]
    linea = orden + ":1"
    comision = por_tipo["comision"]["importe_centavos"]
    envio = por_tipo["envio"]["importe_centavos"]
    neto = por_tipo["liquidacion_neta"]["importe_centavos"]
    fecha = d["fecha_corte"]
    locales = []
    for e in d["eventos"]:
        if e["tipo"] in {"comision", "envio", "pago_bruto", "liquidacion_neta"}:
            continue
        e["lineas"] = [linea]
        locales.append(e)
    ml = {"formato": FORMATO_ML, "organizacion_id": d["organizacion_id"],
        "unidad_negocio_id": d["unidad_negocio_id"], "cuenta_codigo": CUENTA,
        "seller_id": seller, "fecha_corte": fecha,
        "ordenes": [{"id": orden, "status": "paid", "pack_id": None,
            "seller": {"id": seller}, "currency_id": "ARS", "date_created": x["fecha_venta"],
            "shipping": {"id": shipment}, "total_amount": dinero(x["precio_unitario_centavos"]),
            "context": {"site": "MLA", "flows": []}, "order_items": [{
                "item": {"id": x["publicacion_id"], "seller_sku": x["sku"], "variation_id": x.get("variante_id") or None},
                "quantity": 1, "unit_price": dinero(x["precio_unitario_centavos"]),
                "currency_id": "ARS", "sale_fee": dinero(comision)}]}],
        "publicaciones": [{"id": x["publicacion_id"], "seller_id": seller, "currency_id": "ARS",
            "title": "Publicación ficticia del producto " + x["sku"]}],
        "costos_envio": [{"shipment_id": shipment, "fecha": fecha,
            "respuesta": {"senders": [{"user_id": seller, "cost": dinero(envio)}]}}],
        "datos_locales": {"lineas": [{"order_id": orden, "referencia_linea": "1", "sku": x["sku"],
            "costo_snapshot": x["costo_snapshot"], "previsto": x["previsto"]}],
            "eventos": locales, "cobertura": d["cobertura"],
            "gastos_locales_previstos_centavos": d["gastos_locales_previstos_centavos"],
            "cargos_ml_incluidos_en_neto": True, "enlace_precio": d["enlace_precio"]}}
    respuesta = {"id": pago, "collector_id": seller, "currency_id": "ARS", "status": "approved",
        "operation_type": "regular_payment", "date_approved": fecha, "date_last_updated": fecha,
        "transaction_amount": dinero(x["precio_unitario_centavos"]), "transaction_amount_refunded": 0,
        "refunds": [], "transaction_details": {"net_received_amount": dinero(neto)},
        "fee_details": [{"type": "mercadopago_fee", "fee_payer": "collector", "amount": dinero(comision)},
            {"type": "shipping_fee", "fee_payer": "collector", "amount": dinero(envio)}]}
    if caso == "sin_neto":
        respuesta["transaction_details"].pop("net_received_amount")
    elif caso == "cargo_diferente":
        if neto < 10000:
            raise ValueError("El neto del ensayo no admite este caso de comisión adicional.")
        respuesta["fee_details"][0]["amount"] = dinero(comision + 10000)
        respuesta["transaction_details"]["net_received_amount"] = dinero(neto - 10000)
    return {"formato": FORMATO_MP, "snapshot_ml": ml, "collector_id": seller,
        "pagos_mp": [{"ordenes": [orden], "referencia_vinculo": "Vínculo ficticio del mismo ensayo por orden original",
            "respuesta": respuesta, "relaciones_cargos": [
                {"indice": 0, "hechos_ml": [f"ml-comision:{linea}"], "referencia": "Misma comisión sintética"},
                {"indice": 1, "hechos_ml": [f"ml-envio:{shipment}"], "referencia": "Mismo envío sintético"}]}]}
