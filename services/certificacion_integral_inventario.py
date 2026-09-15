"""Certificación integral y de solo lectura del inventario por tenant."""

import hashlib
import io
import json


def certificar_inventario(*, organizacion_id, datos):
    """Audita relaciones y cantidades locales sin modificar stock ni colas."""
    colecciones = {
        nombre: [x for x in datos.get(nombre, []) if getattr(x, "organizacion_id", organizacion_id) == organizacion_id]
        for nombre in (
            "sucursales", "existencias", "movimientos", "items_inventario", "reservas",
            "transferencias", "conteos", "eventos_inventario_pedidos", "eventos_canal_inventario",
            "propuestas_publicacion_inventario",
        )
    }
    hallazgos = []

    def agregar(codigo, entidad, identificador, detalle):
        hallazgos.append({"codigo": codigo, "entidad": entidad, "id": identificador, "detalle": detalle})

    sucursal_ids = {x.id for x in colecciones["sucursales"]}
    item_ids = {x.id for x in colecciones["items_inventario"]}
    existencia_ids = {x.id for x in colecciones["existencias"]}
    pares = set()
    skus = set()
    claves_reserva = set()
    claves_evento = set()

    for item in colecciones["items_inventario"]:
        sku = str(getattr(item, "sku", "") or "").strip().lower()
        if not sku or sku in skus:
            agregar("sku_duplicado", "item", item.id, "El SKU está vacío o repetido dentro del tenant.")
        skus.add(sku)

    for existencia in colecciones["existencias"]:
        par = (existencia.sucursal_operativa_id, existencia.item_inventario_id)
        if existencia.sucursal_operativa_id not in sucursal_ids:
            agregar("sucursal_ajena", "existencia", existencia.id, "La sucursal no pertenece al tenant.")
        if existencia.item_inventario_id is not None and existencia.item_inventario_id not in item_ids:
            agregar("item_ajeno", "existencia", existencia.id, "El ítem no pertenece al tenant.")
        if par in pares:
            agregar("existencia_duplicada", "existencia", existencia.id, "Hay más de una existencia para el mismo ítem y sucursal.")
        pares.add(par)
        actual = int(getattr(existencia, "stock_actual", 0) or 0)
        reservado = int(getattr(existencia, "stock_reservado", 0) or 0)
        bloqueado = int(getattr(existencia, "stock_bloqueado", 0) or 0)
        transito = int(getattr(existencia, "stock_transito", 0) or 0)
        minimo = int(getattr(existencia, "stock_minimo", 0) or 0)
        maximo = getattr(existencia, "stock_maximo", None)
        if min(actual, reservado, bloqueado, transito, minimo) < 0 or reservado + bloqueado > actual:
            agregar("cantidades_inconsistentes", "existencia", existencia.id, "Las cantidades son negativas o exceden el stock actual.")
        if maximo is not None and int(maximo) < minimo:
            agregar("limites_invertidos", "existencia", existencia.id, "El stock máximo es menor al mínimo.")

    for movimiento in colecciones["movimientos"]:
        if movimiento.existencia_sucursal_id not in existencia_ids:
            agregar("movimiento_huerfano", "movimiento", movimiento.id, "La existencia asociada quedó fuera del tenant.")
        actual_anterior = int(getattr(movimiento, "stock_actual_anterior", 0) or 0)
        actual_nuevo = int(getattr(movimiento, "stock_actual_nuevo", 0) or 0)
        reservado_anterior = int(getattr(movimiento, "stock_reservado_anterior", 0) or 0)
        reservado_nuevo = int(getattr(movimiento, "stock_reservado_nuevo", 0) or 0)
        if min(actual_anterior, actual_nuevo, reservado_anterior, reservado_nuevo) < 0:
            agregar("movimiento_negativo", "movimiento", movimiento.id, "El movimiento contiene un saldo negativo.")

    for reserva in colecciones["reservas"]:
        clave = str(getattr(reserva, "clave_idempotencia", "") or "").strip()
        if reserva.existencia_sucursal_id not in existencia_ids:
            agregar("reserva_huerfana", "reserva", reserva.id, "La reserva apunta fuera del tenant.")
        if not clave or clave in claves_reserva:
            agregar("reserva_no_idempotente", "reserva", reserva.id, "La clave está vacía o repetida.")
        claves_reserva.add(clave)
        if int(getattr(reserva, "cantidad", 0) or 0) <= 0:
            agregar("reserva_invalida", "reserva", reserva.id, "La cantidad reservada no es positiva.")

    for transferencia in colecciones["transferencias"]:
        solicitada = int(getattr(transferencia, "cantidad_solicitada", 0) or 0)
        despachada = int(getattr(transferencia, "cantidad_despachada", 0) or 0)
        recibida = int(getattr(transferencia, "cantidad_recibida", 0) or 0)
        if transferencia.existencia_origen_id not in existencia_ids or transferencia.existencia_destino_id not in existencia_ids:
            agregar("transferencia_huerfana", "transferencia", transferencia.id, "El origen o destino quedó fuera del tenant.")
        if transferencia.existencia_origen_id == transferencia.existencia_destino_id:
            agregar("transferencia_mismo_destino", "transferencia", transferencia.id, "El origen y destino son iguales.")
        if solicitada <= 0 or not 0 <= recibida <= despachada <= solicitada:
            agregar("cantidades_transferencia_invalidas", "transferencia", transferencia.id, "Las cantidades no respetan la secuencia solicitada, despachada y recibida.")

    for conteo in colecciones["conteos"]:
        if conteo.sucursal_operativa_id not in sucursal_ids:
            agregar("conteo_huerfano", "conteo", conteo.id, "El conteo pertenece a otra sucursal o tenant.")

    for nombre in ("eventos_inventario_pedidos", "eventos_canal_inventario"):
        for evento in colecciones[nombre]:
            clave = (nombre, str(getattr(evento, "clave_idempotencia", "") or "").strip())
            if not clave[1] or clave in claves_evento:
                agregar("evento_no_idempotente", "evento", evento.id, "La clave está vacía o repetida.")
            claves_evento.add(clave)

    propuestas_ejecutables = 0
    for propuesta in colecciones["propuestas_publicacion_inventario"]:
        if getattr(propuesta, "puede_ejecutar", False):
            propuestas_ejecutables += 1
            agregar("propuesta_ejecutable", "propuesta", propuesta.id, "Una propuesta offline quedó marcada como ejecutable.")

    configuracion = datos.get("automatizacion_pedidos")
    automatizacion_activa = bool(
        configuracion
        and getattr(configuracion, "organizacion_id", None) == organizacion_id
        and getattr(configuracion, "estado", "desactivado") == "activo"
    )
    if automatizacion_activa:
        agregar("automatizacion_activa", "configuracion", configuracion.id, "La automatización pedido-inventario está activa.")

    resumen = {nombre: len(valores) for nombre, valores in colecciones.items()}
    resumen.update({
        "combinaciones_faltantes": len(datos.get("combinaciones_faltantes", [])),
        "hallazgos": len(hallazgos),
        "propuestas_ejecutables": propuestas_ejecutables,
    })
    resultado = {
        "organizacion_id": organizacion_id,
        "modo": "offline",
        "aprobado": not hallazgos,
        "resumen": resumen,
        "hallazgos": hallazgos,
        "controles": {
            "aislamiento_tenant": True,
            "automatizacion_pedidos": False,
            "publicaciones_canales": 0,
            "reservas_creadas": 0,
            "movimientos_creados": 0,
            "acciones_externas": 0,
            "escrituras": 0,
        },
    }
    resultado["huella_control"] = hashlib.sha256(
        json.dumps(resultado, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return resultado


def exportar_certificacion(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
