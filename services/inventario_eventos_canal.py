"""Contratos multicanal preparados; no están conectados a webhooks ni stock."""

import hashlib
import json

from services.inventario_pedidos import agrupar_items_pedido


TIPOS_EVENTO = frozenset({
    "reservar", "liberar", "consumir", "revisar_devolucion",
})


def normalizar_cantidades(cantidades):
    normalizadas = {}
    if isinstance(cantidades, dict):
        pares = cantidades.items()
    else:
        pares = agrupar_items_pedido(cantidades).items()
    for sku, cantidad in pares:
        sku_normalizado = str(sku or "").strip().upper()
        try:
            cantidad_normalizada = int(cantidad or 0)
        except (TypeError, ValueError) as error:
            raise ValueError("Las cantidades del evento deben ser enteras.") from error
        if sku_normalizado and cantidad_normalizada > 0:
            normalizadas[sku_normalizado] = (
                normalizadas.get(sku_normalizado, 0) + cantidad_normalizada
            )
    if not normalizadas:
        raise ValueError("El evento no contiene cantidades inventariables.")
    return normalizadas


def crear_contrato_evento(
    *, canal, referencia, tipo_evento, cantidades, estado_origen="", parcial=False,
):
    tipo = str(tipo_evento or "").strip().lower()
    if tipo not in TIPOS_EVENTO:
        raise ValueError("El tipo de evento multicanal no es válido.")
    canal_normalizado = str(canal or "").strip().lower().replace(" ", "_")
    referencia_normalizada = str(referencia or "").strip()
    if not canal_normalizado or not referencia_normalizada:
        raise ValueError("El evento necesita canal y referencia externa.")
    cantidades_normalizadas = normalizar_cantidades(cantidades)
    return {
        "version": 1,
        "canal": canal_normalizado,
        "referencia": referencia_normalizada,
        "tipo_evento": tipo,
        "cantidades": cantidades_normalizadas,
        "parcial": bool(parcial),
        "estado_origen": str(estado_origen or "").strip().lower(),
        "requiere_revision": tipo == "revisar_devolucion",
        "modo": "desconectado",
    }


def contrato_desde_pedido(pedido, *, evento_externo=None, cantidades=None):
    """Traduce estados conocidos sin ejecutar el contrato resultante."""
    canal = str(getattr(pedido, "canal", "") or "").strip()
    estado = str(
        evento_externo
        or getattr(pedido, "estado", "")
        or ""
    ).strip().lower()
    if any(valor in estado for valor in ("cancel", "anulad")):
        tipo = "liberar"
    elif any(valor in estado for valor in ("devol", "return", "refund")):
        tipo = "revisar_devolucion"
    elif any(valor in estado for valor in ("despach", "shipped", "fulfilled")):
        tipo = "consumir"
    else:
        tipo = "reservar"
    referencia = (
        getattr(pedido, "id_venta", None)
        or getattr(pedido, "ml_pack_id", None)
        or getattr(pedido, "tn_order_id", None)
        or getattr(pedido, "id", None)
    )
    return crear_contrato_evento(
        canal=canal,
        referencia=referencia,
        tipo_evento=tipo,
        cantidades=cantidades if cantidades is not None else getattr(pedido, "items", ()),
        estado_origen=estado,
        parcial=cantidades is not None,
    )


def contrato_puede_ejecutarse(contrato, configuracion):
    """Permanece falso mientras el adaptador esté desconectado de producción."""
    return bool(
        contrato
        and contrato.get("modo") == "productivo"
        and str(getattr(configuracion, "estado", "")) == "activo"
    )


def resolver_identidad_cuenta(pedido):
    """Exige la cuenta exacta que originó el pedido; nunca infiere por canal."""
    canal = str(getattr(pedido, "canal", "") or "").strip().lower()
    if "mercado" in canal:
        cuenta_id = int(getattr(pedido, "ml_cuenta_id", 0) or 0)
        cuenta_tipo = "mercado_libre"
    elif "tienda" in canal:
        cuenta_id = int(getattr(pedido, "tn_cuenta_id", 0) or 0)
        cuenta_tipo = "tienda_nube"
    else:
        raise ValueError("El pedido no conserva un canal empresarial compatible.")
    if not cuenta_id:
        raise ValueError("El pedido no conserva la cuenta empresarial de origen.")
    return cuenta_tipo, cuenta_id


def preparar_sobre_evento(
    pedido,
    *,
    organizacion_id,
    evento_externo_id,
    evento_externo=None,
    cantidades=None,
):
    """Crea un sobre auditable y determinista sin persistir ni ejecutar stock."""
    identificador_evento = str(evento_externo_id or "").strip()
    if not identificador_evento:
        raise ValueError("El evento necesita un identificador externo idempotente.")
    cuenta_tipo, cuenta_id = resolver_identidad_cuenta(pedido)
    contrato = contrato_desde_pedido(
        pedido,
        evento_externo=evento_externo,
        cantidades=cantidades,
    )
    contenido = {
        "organizacion_id": int(organizacion_id),
        "pedido_id": int(getattr(pedido, "id", 0) or 0),
        "cuenta_tipo": cuenta_tipo,
        "cuenta_id": cuenta_id,
        "evento_externo_id": identificador_evento,
        "contrato": contrato,
    }
    serializado = json.dumps(
        contenido, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    payload_hash = hashlib.sha256(serializado.encode("utf-8")).hexdigest()
    clave = (
        f"org:{int(organizacion_id)}:{cuenta_tipo}:{cuenta_id}:"
        f"evento:{identificador_evento}"
    )
    return {
        **contenido,
        "clave_idempotencia": clave,
        "payload_hash": payload_hash,
        "estado": "preparado_sin_conexion",
        "contrato_json": serializado,
    }


def registrar_sobre_desconectado(sobre, *, EventoCanal, db_session):
    """Registra una sola vez el contrato; no invoca reservas ni movimientos."""
    organizacion_id = int(sobre["organizacion_id"])
    clave = str(sobre["clave_idempotencia"])
    existente = EventoCanal.query.filter_by(
        organizacion_id=organizacion_id,
        clave_idempotencia=clave,
    ).first()
    if existente is not None:
        if str(existente.payload_hash) != str(sobre["payload_hash"]):
            raise ValueError(
                "La clave externa ya existe con un contenido diferente."
            )
        return existente, False
    contrato = sobre["contrato"]
    evento = EventoCanal(
        organizacion_id=organizacion_id,
        pedido_id=sobre["pedido_id"],
        canal=contrato["canal"],
        cuenta_tipo=sobre["cuenta_tipo"],
        cuenta_id=sobre["cuenta_id"],
        referencia_externa=contrato["referencia"],
        evento_externo_id=sobre["evento_externo_id"],
        tipo_evento=contrato["tipo_evento"],
        clave_idempotencia=clave,
        estado="preparado_sin_conexion",
        parcial=bool(contrato["parcial"]),
        requiere_revision=bool(contrato["requiere_revision"]),
        contrato_json=sobre["contrato_json"],
        payload_hash=sobre["payload_hash"],
    )
    db_session.add(evento)
    db_session.commit()
    return evento, True


def _normalizar_canal(valor):
    return str(valor or "").strip().lower().replace(" ", "_")


def resolver_vinculo_sobre(sobre, vinculos):
    """Resuelve un único vínculo activo dentro del tenant del sobre."""
    organizacion_id = int(sobre["organizacion_id"])
    cuenta_tipo = str(sobre["cuenta_tipo"])
    cuenta_id = int(sobre["cuenta_id"])
    atributo = {
        "mercado_libre": "mercado_libre_cuenta_id",
        "tienda_nube": "tienda_nube_cuenta_id",
    }.get(cuenta_tipo)
    if atributo is None:
        return None, "El tipo de cuenta del evento no es compatible."
    candidatos = [
        vinculo for vinculo in vinculos
        if int(getattr(vinculo, "organizacion_id", 0) or 0) == organizacion_id
        and int(getattr(vinculo, atributo, 0) or 0) == cuenta_id
    ]
    if len(candidatos) != 1:
        return None, "La cuenta no posee un vínculo empresarial único en el tenant."
    vinculo = candidatos[0]
    if str(getattr(vinculo, "estado", "")) != "activo":
        return None, "El vínculo empresarial de la cuenta está desactivado."
    return vinculo, None


def validar_sobre_evento(
    sobre,
    *,
    configuracion,
    vinculos,
    items_inventario,
    existencias,
    reservas=(),
):
    """Calcula bloqueos y deltas previstos; jamás modifica modelos ni sesión."""
    contrato = sobre["contrato"]
    organizacion_id = int(sobre["organizacion_id"])
    bloqueos = []
    vinculo, error_vinculo = resolver_vinculo_sobre(sobre, vinculos)
    if error_vinculo:
        bloqueos.append(error_vinculo)
    sucursal_id = int(
        getattr(configuracion, "sucursal_operativa_id", 0)
        or getattr(vinculo, "sucursal_operativa_id", 0)
        or 0
    )
    if not sucursal_id:
        bloqueos.append("El evento no tiene una ubicación operativa resoluble.")
    if str(getattr(configuracion, "estado", "desactivado")) != "activo":
        bloqueos.append("La automatización productiva está desactivada.")

    items_por_sku = {
        str(getattr(item, "sku", "") or "").strip().upper(): item
        for item in items_inventario
        if int(getattr(item, "organizacion_id", 0) or 0) == organizacion_id
    }
    existencias_por_item = {
        int(getattr(existencia, "item_inventario_id", 0) or 0): existencia
        for existencia in existencias
        if int(getattr(existencia, "organizacion_id", 0) or 0) == organizacion_id
        and int(getattr(existencia, "sucursal_operativa_id", 0) or 0)
        == sucursal_id
    }
    canal_evento = _normalizar_canal(contrato["canal"])
    referencia = str(contrato["referencia"])
    lineas = []
    for sku, cantidad in contrato["cantidades"].items():
        errores = []
        item = items_por_sku.get(sku)
        existencia = None
        if item is None:
            errores.append("SKU no preparado")
        else:
            if not bool(getattr(item, "activo", False)):
                errores.append("SKU desactivado")
            existencia = existencias_por_item.get(
                int(getattr(item, "id", 0) or 0)
            )
            if existencia is None:
                errores.append("Sin existencia en la ubicación")
            elif not bool(getattr(existencia, "control_activo", False)):
                errores.append("Control de existencia desactivado")

        actual = reservado_total = bloqueado = disponible = None
        reserva_evento = 0
        delta_actual = delta_reservado = 0
        if existencia is not None:
            actual = int(getattr(existencia, "stock_actual", 0) or 0)
            reservado_total = int(
                getattr(existencia, "stock_reservado", 0) or 0
            )
            bloqueado = int(getattr(existencia, "stock_bloqueado", 0) or 0)
            disponible = actual - reservado_total - bloqueado
            reserva_evento = sum(
                int(getattr(reserva, "cantidad", 0) or 0)
                for reserva in reservas
                if int(getattr(reserva, "organizacion_id", 0) or 0)
                == organizacion_id
                and int(getattr(reserva, "existencia_sucursal_id", 0) or 0)
                == int(getattr(existencia, "id", 0) or 0)
                and str(getattr(reserva, "estado", "")) == "activa"
                and _normalizar_canal(getattr(reserva, "canal", ""))
                == canal_evento
                and str(getattr(reserva, "referencia_externa", "") or "")
                == referencia
            )
            if contrato["tipo_evento"] == "reservar":
                if disponible < cantidad:
                    errores.append("Stock disponible insuficiente")
                delta_reservado = cantidad
            elif contrato["tipo_evento"] in {"liberar", "consumir"}:
                if reserva_evento < cantidad:
                    errores.append("Reserva identificada insuficiente")
                delta_reservado = -cantidad
                if contrato["tipo_evento"] == "consumir":
                    delta_actual = -cantidad

        if contrato["requiere_revision"]:
            delta_actual = delta_reservado = 0
        lineas.append({
            "sku": sku,
            "cantidad": cantidad,
            "actual": actual,
            "reservado_total": reservado_total,
            "reserva_evento": reserva_evento,
            "bloqueado": bloqueado,
            "disponible": disponible,
            "delta_actual": delta_actual,
            "delta_reservado": delta_reservado,
            "resultado": "bloqueado" if errores else "listo",
            "errores": errores,
        })
        bloqueos.extend(f"{sku}: {error}." for error in errores)

    if bloqueos:
        estado = "bloqueado"
    elif contrato["requiere_revision"]:
        estado = "revision_manual"
    else:
        estado = "listo_sin_ejecutar"
    return {
        "organizacion_id": organizacion_id,
        "pedido_id": int(sobre["pedido_id"]),
        "cuenta_tipo": sobre["cuenta_tipo"],
        "cuenta_id": int(sobre["cuenta_id"]),
        "sucursal_operativa_id": sucursal_id,
        "tipo_evento": contrato["tipo_evento"],
        "parcial": bool(contrato["parcial"]),
        "estado": estado,
        "lineas": lineas,
        "bloqueos": list(dict.fromkeys(bloqueos)),
        "puede_ejecutar": False,
        "modo": "prevalidacion",
    }


def cargar_sobre_persistido(evento):
    """Reconstruye y verifica un sobre guardado sin modificar su estado."""
    try:
        contenido = json.loads(str(getattr(evento, "contrato_json", "") or ""))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("El contrato guardado no contiene JSON valido.") from error
    if not isinstance(contenido, dict) or not isinstance(
        contenido.get("contrato"), dict
    ):
        raise ValueError("El contrato guardado esta incompleto.")
    serializado = json.dumps(
        contenido, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    huella = hashlib.sha256(serializado.encode("utf-8")).hexdigest()
    if huella != str(getattr(evento, "payload_hash", "") or ""):
        raise ValueError("La huella del contrato guardado no coincide.")
    return {
        **contenido,
        "clave_idempotencia": str(
            getattr(evento, "clave_idempotencia", "") or ""
        ),
        "payload_hash": huella,
        "estado": str(getattr(evento, "estado", "") or ""),
        "contrato_json": serializado,
    }


def diagnosticar_eventos_persistidos(
    eventos,
    *,
    configuracion,
    vinculos,
    items_inventario,
    existencias,
    reservas=(),
):
    """Prevalida la bandeja completa; nunca persiste estados ni mueve stock."""
    diagnosticos = {}
    resumen = {
        "total": 0,
        "listos": 0,
        "bloqueados": 0,
        "revision_manual": 0,
        "invalidos": 0,
    }
    for evento in eventos:
        evento_id = int(getattr(evento, "id", 0) or 0)
        resumen["total"] += 1
        try:
            sobre = cargar_sobre_persistido(evento)
            diagnostico = validar_sobre_evento(
                sobre,
                configuracion=configuracion,
                vinculos=vinculos,
                items_inventario=items_inventario,
                existencias=existencias,
                reservas=reservas,
            )
        except (KeyError, TypeError, ValueError) as error:
            diagnostico = {
                "estado": "invalido",
                "bloqueos": [str(error)],
                "lineas": [],
                "puede_ejecutar": False,
                "modo": "prevalidacion",
            }
        estado = diagnostico["estado"]
        if estado == "listo_sin_ejecutar":
            resumen["listos"] += 1
        elif estado == "revision_manual":
            resumen["revision_manual"] += 1
        elif estado == "invalido":
            resumen["invalidos"] += 1
        else:
            resumen["bloqueados"] += 1
        diagnosticos[evento_id] = diagnostico
    return diagnosticos, resumen
