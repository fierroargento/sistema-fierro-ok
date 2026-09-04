"""Relaciona eventos de staging y proyecta efectos sin escribir en el dominio."""

import json


ORDEN = {"publicacion": 10, "comision": 20, "envio": 30, "promocion": 40, "venta": 50, "pago": 60, "devolucion": 70}


def _leer(evento):
    try: sobre = json.loads(evento.payload_json)
    except (TypeError, json.JSONDecodeError) as error: raise ValueError("El evento contiene JSON invalido.") from error
    datos = sobre.get("datos")
    if not isinstance(datos, dict): raise ValueError("El evento no contiene datos normalizados.")
    tipo = sobre.get("tipo")
    if tipo not in ORDEN: raise ValueError("El tipo normalizado no es valido.")
    return {"id": evento.id, "canal": evento.canal, "cuenta_codigo": evento.cuenta_codigo, "tipo": tipo, "referencia": sobre.get("referencia"), "datos": datos, "estado_staging": evento.estado}


def orquestar_eventos(eventos):
    normalizados = []; errores = []
    for evento in eventos:
        try: normalizados.append(_leer(evento))
        except ValueError as error: errores.append({"evento_id": getattr(evento, "id", None), "error": str(error)})
    normalizados.sort(key=lambda item: (ORDEN[item["tipo"]], item["id"]))
    ventas = {str(e["datos"].get("venta_id")): e for e in normalizados if e["tipo"] == "venta" and e["datos"].get("venta_id") is not None}
    publicaciones = {str(e["datos"].get("publicacion_id")): e for e in normalizados if e["tipo"] == "publicacion" and e["datos"].get("publicacion_id") is not None}
    cadenas = {}; propuestas = []; alertas = []
    for venta_id, venta in ventas.items(): cadenas[venta_id] = {"venta": venta, "pagos": [], "devoluciones": [], "estado_proyectado": "venta_observada"}
    for evento in normalizados:
        tipo = evento["tipo"]; datos = evento["datos"]
        if tipo == "pago":
            venta_id = str(datos.get("venta_id") or "")
            if venta_id not in cadenas: alertas.append({"codigo": "pago_huerfano", "evento": evento, "detalle": f"No existe la venta {venta_id}."})
            else:
                cadenas[venta_id]["pagos"].append(evento); cadenas[venta_id]["estado_proyectado"] = "pago_observado"
                propuestas.append({"tipo": "conciliar_pago", "venta_id": venta_id, "detalle": "Comparar neto recibido con liquidacion esperada."})
        elif tipo == "devolucion":
            venta_id = str(datos.get("venta_id") or "")
            if venta_id not in cadenas: alertas.append({"codigo": "devolucion_huerfana", "evento": evento, "detalle": f"No existe la venta {venta_id}."})
            else:
                cadenas[venta_id]["devoluciones"].append(evento); cadenas[venta_id]["estado_proyectado"] = "devolucion_observada"
                propuestas.append({"tipo": "revisar_devolucion", "venta_id": venta_id, "detalle": "Recalcular saldo y piso economico sin ejecutar reintegros."})
        elif tipo == "promocion" and datos.get("activa"):
            propuestas.append({"tipo": "revisar_promocion", "publicacion_id": str(datos.get("publicacion_id") or evento["referencia"]).split(":")[0], "detalle": "Cancelar antes de un cambio de precio si la liquidacion queda bajo el piso."})
        elif tipo == "venta":
            for item in datos.get("items") or []:
                publicacion_id = str(item.get("referencia_item") or "")
                if publicacion_id and publicacion_id not in publicaciones:
                    alertas.append({"codigo": "publicacion_faltante", "evento": evento, "detalle": f"El item {publicacion_id} no tiene publicacion en el lote."})
    efectos = []
    for evento in normalizados:
        efectos.append({"evento_id": evento["id"], "tipo": evento["tipo"], "antes": evento["estado_staging"], "despues": "validado_simulado", "escritura_dominio": False})
    resumen = {"eventos": len(normalizados), "ventas": len(ventas), "cadenas_completas": sum(bool(c["pagos"]) for c in cadenas.values()), "alertas": len(alertas), "propuestas": len(propuestas), "errores": len(errores)}
    return {"eventos": normalizados, "cadenas": list(cadenas.values()), "alertas": alertas, "propuestas": propuestas, "efectos": efectos, "errores": errores, "resumen": resumen, "acciones_externas": 0, "escrituras_dominio": 0}
