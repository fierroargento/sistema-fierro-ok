"""Items, evidencias y control final de postventa sin efectos operativos."""

import hashlib
import io
import json
from decimal import Decimal, InvalidOperation

from services.fechas import ahora_utc_naive
from services.postventa_preparatoria import _validar_caso_pedido


def agregar_item(datos, *, caso, pedido, producto, organizacion_id,
                 unidad_negocio_id, Item, db_session):
    _validar_caso_pedido(caso, pedido, organizacion_id, unidad_negocio_id)
    if producto is None or int(producto.organizacion_id) != int(organizacion_id):
        raise ValueError("El producto no pertenece a la organización activa.")
    try:
        cantidad = Decimal(str(datos.get("cantidad") or "0").replace(",", "."))
    except InvalidOperation as error:
        raise ValueError("Cantidad inválida.") from error
    condicion = str(datos.get("condicion") or "sin_recibir")
    detalle = str(datos.get("detalle_item") or "").strip()
    if (not cantidad.is_finite()
            or not 0 < cantidad <= Decimal("9999999999.9999")
            or condicion not in {"sin_recibir", "nuevo", "usado", "danado", "incompleto"}
            or len(detalle) > 500):
        raise ValueError("Cantidad, condición o detalle inválidos.")
    item = Item(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
        caso_id=caso.id, producto_id=producto.id, cantidad=cantidad,
        condicion=condicion, detalle=detalle or None, recibido=False,
        afecta_stock=False,
    )
    db_session.add(item)
    db_session.commit()
    return item


def agregar_evidencia(datos, *, caso, pedido, organizacion_id,
                      unidad_negocio_id, Evidencia, db_session):
    _validar_caso_pedido(caso, pedido, organizacion_id, unidad_negocio_id)
    tipo = str(datos.get("tipo_evidencia") or "").strip()
    referencia = str(datos.get("referencia") or "").strip()
    if (tipo not in {"foto", "video", "documento", "nota_interna"}
            or not 5 <= len(referencia) <= 500):
        raise ValueError("Tipo y referencia de evidencia no son válidos.")
    huella = hashlib.sha256(f"{caso.id}|{tipo}|{referencia}".encode()).hexdigest()
    evidencia = Evidencia(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
        caso_id=caso.id, tipo=tipo, referencia=referencia, huella=huella,
        verificada=False, enviada=False,
    )
    db_session.add(evidencia)
    db_session.commit()
    return evidencia


def control_final(*, organizacion_id, unidad_negocio_id, casos, propuestas,
                  items, evidencias, ahora=None):
    ahora = ahora or ahora_utc_naive()
    casos = [x for x in casos if int(x.organizacion_id) == int(organizacion_id)
             and int(x.unidad_negocio_id) == int(unidad_negocio_id)]
    ids = {x.id for x in casos}
    propuestas = [x for x in propuestas if x.caso_id in ids
                   and int(x.organizacion_id) == int(organizacion_id)
                   and int(x.unidad_negocio_id) == int(unidad_negocio_id)]
    items = [x for x in items if x.caso_id in ids
             and int(x.organizacion_id) == int(organizacion_id)
             and int(x.unidad_negocio_id) == int(unidad_negocio_id)]
    evidencias = [x for x in evidencias if x.caso_id in ids
                  and int(x.organizacion_id) == int(organizacion_id)
                  and int(x.unidad_negocio_id) == int(unidad_negocio_id)]
    hallazgos = []
    for caso in casos:
        if caso.estado not in {"cancelado", "cerrado_sin_efecto"} and not any(x.caso_id == caso.id for x in items):
            hallazgos.append({"codigo": "caso_sin_items", "caso_id": caso.id})
        if caso.estado in {"diagnostico", "propuesta"} and not any(x.caso_id == caso.id for x in evidencias):
            hallazgos.append({"codigo": "caso_sin_evidencia", "caso_id": caso.id})
        if caso.estado == "propuesta" and not any(x.caso_id == caso.id for x in propuestas):
            hallazgos.append({"codigo": "caso_sin_resolucion", "caso_id": caso.id})
        if caso.estado not in {"cancelado", "cerrado_sin_efecto"} and (ahora - caso.fecha_creacion).days > 15:
            hallazgos.append({"codigo": "caso_vencido", "caso_id": caso.id})
    for item in items:
        if item.recibido or item.afecta_stock:
            hallazgos.append({"codigo": "item_con_stock", "item_id": item.id})
    for evidencia in evidencias:
        if evidencia.verificada or evidencia.enviada:
            hallazgos.append({"codigo": "evidencia_externa", "evidencia_id": evidencia.id})
    resultado = {
        "organizacion_id": int(organizacion_id),
        "unidad_negocio_id": int(unidad_negocio_id),
        "modo": "cierre_postventa_no_ejecutable",
        "aprobado": not hallazgos,
        "resumen": {
            "casos": len(casos), "items": len(items),
            "evidencias": len(evidencias), "propuestas": len(propuestas),
            "exposicion_centavos": sum(int(x.importe_centavos) for x in propuestas),
            "hallazgos": len(hallazgos),
        },
        "hallazgos": hallazgos,
        "controles": {
            "recepciones": 0, "stock_movido": 0, "reintegros": 0,
            "creditos": 0, "mensajes": 0, "acciones_canal": 0,
            "conexiones_externas": 0,
        },
    }
    resultado["huella_control"] = hashlib.sha256(json.dumps(
        resultado, sort_keys=True, separators=(",", ":"), default=str
    ).encode()).hexdigest()
    return resultado


def exportar(resultado):
    return io.BytesIO(json.dumps(
        resultado, ensure_ascii=False, sort_keys=True, indent=2, default=str
    ).encode())
