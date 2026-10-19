"""Traduce snapshots ML declarados al contrato económico existente, sin red/DB."""
from copy import deepcopy
from decimal import Decimal, DecimalException
from hashlib import sha256
import json

from services.adaptadores_offline_canales import adaptar_fixture
from services.rentabilidad_ml_offline import _entero, _fecha, _texto, MAX_CENTAVOS

FORMATO_ML = "ml_rentabilidad_offline_v1"


def _id(valor, campo):
    if isinstance(valor, bool) or not isinstance(valor, (str, int)):
        raise ValueError(f"{campo}: identificador no válido.")
    texto = str(valor).strip()
    if not texto or len(texto) > 80:
        raise ValueError(f"{campo}: identificador no válido.")
    return texto


def _centavos(valor):
    if isinstance(valor, bool) or not isinstance(valor, (int, float, str)):
        raise ValueError("Importe ML ausente o no válido; no se sustituye por cero.")
    try:
        numero = Decimal(str(valor))
        if not numero.is_finite() or not 0 <= numero <= Decimal(MAX_CENTAVOS) / 100:
            raise ValueError()
        exacto = numero.quantize(Decimal("0.01"))
        if numero != exacto:
            raise ValueError()
        return int(exacto * 100)
    except (ValueError, DecimalException, OverflowError):
        raise ValueError("Importe ML no válido: requiere ARS no negativos con hasta dos decimales.") from None


def _lista(valor, nombre, maximo=200):
    if not isinstance(valor, list) or len(valor) > maximo or any(not isinstance(x, dict) for x in valor):
        raise ValueError(f"{nombre}: lista de objetos no válida.")
    return valor


def normalizar_snapshot_ml(documento, *, organizacion_id, unidad_negocio_id, cuenta_codigo):
    d = deepcopy(documento)
    if d.get("formato") != FORMATO_ML:
        raise ValueError("Formato de snapshot ML no compatible.")
    for campo, esperado in (("organizacion_id", organizacion_id), ("unidad_negocio_id", unidad_negocio_id)):
        if _entero(d.get(campo), campo, minimo=1) != esperado:
            raise ValueError("El snapshot no pertenece al contexto activo.")
    if d.get("cuenta_codigo") != cuenta_codigo:
        raise ValueError("El snapshot pertenece a otra cuenta.")
    seller = _id(d.get("seller_id"), "Vendedor declarado")
    corte = _fecha(d.get("fecha_corte"))
    ordenes = _lista(d.get("ordenes"), "Órdenes")
    if not ordenes:
        raise ValueError("Faltan las órdenes originales.")
    ids = [_id(o.get("id"), "Orden") for o in ordenes]
    if len(set(ids)) != len(ids):
        raise ValueError("Orden original repetida.")
    pack = d.get("pack")
    pack_id = None
    if pack is not None:
        if not isinstance(pack, dict):
            raise ValueError("Pack no válido.")
        pack_id = _id(pack.get("id"), "Pack")
        referencias = [_id(x.get("id"), "Orden del pack") for x in _lista(pack.get("orders"), "Referencias del pack")]
        if len(referencias) != len(set(referencias)) or set(referencias) != set(ids):
            raise ValueError("El pack está incompleto o contiene órdenes ajenas/repetidas.")
    elif len(ids) != 1 or ordenes[0].get("pack_id") is not None:
        raise ValueError("Se requiere el listado completo del pack, sin agrupar por SKU.")
    publicaciones = {}
    for p in _lista(d.get("publicaciones", []), "Publicaciones"):
        ident = _id(p.get("id"), "Publicación")
        if ident in publicaciones:
            raise ValueError("Publicación repetida.")
        if _id(p.get("seller_id"), "Vendedor de publicación") != seller or p.get("currency_id") != "ARS":
            raise ValueError("Publicación de otro vendedor o moneda.")
        publicaciones[ident] = p
    locales = d.get("datos_locales")
    if not isinstance(locales, dict):
        raise ValueError("Falta el bloque datos_locales de costos, previsión y cobertura.")
    vinculos = {}
    for x in _lista(locales.get("lineas", []), "Vínculos históricos"):
        clave = (_id(x.get("order_id"), "Orden del vínculo"), _id(x.get("referencia_linea"), "Posición original"))
        if clave in vinculos:
            raise ValueError("Vínculo histórico repetido.")
        vinculos[clave] = x
    cobertura = deepcopy(locales.get("cobertura", {}))
    if not isinstance(cobertura, dict):
        raise ValueError("Cobertura no válida.")
    incluido = locales.get("cargos_ml_incluidos_en_neto")
    if not isinstance(incluido, bool):
        raise ValueError("Declarar cargos_ml_incluidos_en_neto como true o false; no se infiere del pago.")
    eventos = deepcopy(_lista(locales.get("eventos", []), "Hechos complementarios", 1000))
    if any(e.get("tipo") in {"comision", "envio"} for e in eventos):
        raise ValueError("Comisión y envío deben venir de sus snapshots ML, sin duplicarlos como hechos locales.")
    filas, usadas, envios, clasificaciones, usadas_publicaciones = [], set(), {}, [], set()
    comision_completa = True
    descuentos_pendientes = False
    for order, order_id in zip(ordenes, ids):
        if order.get("status") != "paid":
            raise ValueError("Este lector admite órdenes paid. Cancelaciones/devoluciones requieren revisión, no se omiten.")
        if _id((order.get("seller") or {}).get("id"), "Vendedor de orden") != seller:
            raise ValueError("Una orden pertenece a otro vendedor declarado.")
        if pack_id is not None and _id(order.get("pack_id"), "Pack de orden") != pack_id:
            raise ValueError("Una orden no pertenece al pack.")
        if (order.get("context") or {}).get("site") != "MLA":
            raise ValueError("Este lector requiere contexto.site MLA declarado.")
        if order.get("currency_id") != "ARS":
            raise ValueError("La orden requiere moneda ARS.")
        fecha = order.get("date_created")
        if _fecha(fecha) > corte:
            raise ValueError("Orden posterior al corte.")
        items = _lista(order.get("order_items"), "Líneas originales")
        if not items:
            raise ValueError("Una orden no contiene líneas originales.")
        for item in items:
            _entero(item.get("quantity"), "Cantidad ML", minimo=1, maximo=10**6)
            precio_efectivo = _centavos(item.get("unit_price"))
            if item.get("discounts") or (item.get("gross_price") is not None and _centavos(item["gross_price"]) != precio_efectivo * item["quantity"]):
                descuentos_pendientes = True
            if item.get("currency_id") != "ARS":
                raise ValueError("La línea requiere moneda ARS.")
        # Adaptador existente de ventas; previa validación estricta para evitar ceros por ausencia.
        adaptadas = adaptar_fixture("mercado_libre", "venta", {"id": order_id, "status": "paid",
            "date_created": fecha, "order_items": items}, cuenta_codigo=cuenta_codigo)[0]["datos"]["items"]
        for pos, (item, normal) in enumerate(zip(items, adaptadas), 1):
            producto = item.get("item") or {}
            pub = _id(producto.get("id"), "Publicación de línea")
            variante = producto.get("variation_id")
            variante = "" if variante is None else _id(variante, "Variante")
            if pub not in publicaciones:
                raise ValueError("Falta el snapshot de una publicación de la orden.")
            usadas_publicaciones.add(pub)
            clave = (order_id, str(pos)); usadas.add(clave)
            vinculo = vinculos.get(clave, {})
            sku_api = producto.get("seller_sku") or producto.get("seller_custom_field")
            sku = vinculo.get("sku") or sku_api
            _texto(sku, "SKU de línea; se requiere vínculo explícito si ML no lo informa")
            if sku_api and sku_api != sku:
                raise ValueError("El SKU declarado no coincide con la línea ML.")
            ident = f"{order_id}:{pos}"
            fila = {"linea_id": ident, "order_id": order_id, "referencia_linea": str(pos),
                "publicacion_id": pub, "variante_id": variante, "sku": sku,
                "cantidad": normal["cantidad"], "precio_unitario_centavos": normal["precio_unitario_centavos"],
                "fecha_venta": fecha, "costo_snapshot": vinculo.get("costo_snapshot"), "previsto": vinculo.get("previsto")}
            filas.append(fila)
            if len(filas) > 200:
                raise ValueError("El snapshot admite hasta 200 líneas.")
            fee = item.get("sale_fee")
            if fee is None:
                comision_completa = False
            else:
                importe = _centavos(fee) * normal["cantidad"]
                eventos.append(_hecho(f"ml-comision:{ident}", "comision", importe, [ident], d["fecha_corte"],
                    f"/orders/{order_id} · línea {pos}: sale_fee por unidad", incluido))
            shipping = order.get("shipping") or {}
            shipment = shipping.get("id")
            if shipment is not None:
                envios.setdefault(_id(shipment, "Envío"), []).append(ident)
        if order.get("total_amount") is not None and _centavos(order["total_amount"]) != sum(_centavos(i["unit_price"]) * i["quantity"] for i in items):
            raise ValueError("El total de orden difiere de sus líneas; requiere revisión de descuentos y alcance.")
        contexto = order.get("context") or {}
        flows, tags = contexto.get("flows", []), order.get("tags", [])
        if not isinstance(flows, list) or not isinstance(tags, list):
            raise ValueError("Contexto/tags de la orden no válidos.")
        clasificaciones.append({"order_id": order_id, "tipo": "b2b" if "b2b" in flows or "b2b" in tags else "no_determinado"})
    if set(vinculos) - usadas or set(publicaciones) != usadas_publicaciones:
        raise ValueError("Hay vínculos o publicaciones ajenos al alcance del archivo.")
    # No se importa la cobertura de comisión/envío del archivo como confirmación ciega.
    cobertura["comision"] = {"estado": "confirmado", "referencia": "sale_fee en todas las líneas de órdenes declaradas"} if comision_completa else {"estado": "pendiente"}
    vistos_envio, lineas_envio = set(), set()
    for dato in _lista(d.get("costos_envio", []), "Costos de envío"):
        ident = _id(dato.get("shipment_id"), "Costo de envío")
        if ident in vistos_envio or ident not in envios:
            raise ValueError("Costo de envío repetido o ajeno a las órdenes.")
        vistos_envio.add(ident)
        if _fecha(dato.get("fecha")) > corte:
            raise ValueError("Costo de envío posterior al corte.")
        respuesta = dato.get("respuesta")
        if not isinstance(respuesta, dict):
            raise ValueError("Falta respuesta de costos del envío.")
        senders = _lista(respuesta.get("senders"), "Remitentes de envío")
        propios = [s for s in senders if _id(s.get("user_id"), "Remitente") == seller]
        if len(propios) > 1:
            raise ValueError("Costo del vendedor ambiguo en el envío.")
        if propios and propios[0].get("cost") is not None:
            eventos.append(_hecho(f"ml-envio:{ident}", "envio", _centavos(propios[0]["cost"]), envios[ident], dato["fecha"],
                f"/shipments/{ident}/costs · costo del vendedor declarado", incluido))
            lineas_envio.update(envios[ident])
    cobertura["envio"] = {"estado": "confirmado", "referencia": "senders.cost de todos los envíos declarados"} if lineas_envio == {f["linea_id"] for f in filas} else {"estado": "pendiente"}
    if descuentos_pendientes:
        cobertura["descuentos"] = {"estado": "pendiente"}
    traza = {"formato": FORMATO_ML, "huella_snapshot": sha256(json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()).hexdigest(),
        "seller_declarado": seller, "pack_id": pack_id, "ordenes": clasificaciones,
        "publicaciones": [{"id": p, "titulo": str(publicaciones[p].get("title") or "")[:200]} for p in sorted(publicaciones)],
        "advertencias": ["Snapshot declarado: no verifica autenticidad ni pertenencia externa.",
            "Se conserva posición original por orden; cambios de orden del array requieren otra revisión.",
            "Precio histórico desde unit_price; precio actual de publicación y paid_amount no son precio histórico ni neto.",
            "sale_fee observado en el snapshot no acredita todos los cargos finales ni cobertura de facturación/MP."]}
    entrada = {"version": 1, "organizacion_id": organizacion_id, "unidad_negocio_id": unidad_negocio_id,
        "cuenta_codigo": cuenta_codigo, "moneda": "ARS", "origen": "archivo_offline",
        "referencia_venta": pack_id or ids[0], "fecha_corte": d["fecha_corte"],
        "lineas": filas, "eventos": eventos, "cobertura": cobertura,
        "gastos_locales_previstos_centavos": locales.get("gastos_locales_previstos_centavos"),
        "trazabilidad_ml": traza}
    if "enlace_precio" in locales:
        entrada["enlace_precio"] = deepcopy(locales["enlace_precio"])
        entrada["pendientes_fuente"] = ["Fotografía interna vinculada a un snapshot ML declarado; sin autenticación externa"]
    return entrada


def _hecho(ident, tipo, importe, lineas, fecha, fuente, incluido):
    return {"hecho_id": ident, "tipo": tipo, "importe_centavos": importe, "direccion": "debito",
        "lineas": list(lineas), "fuente": fuente, "fecha": fecha,
        "estado": "observado" if importe else "cero_confirmado", "impacta_saldo": True,
        "incluido_en_neto": incluido}
