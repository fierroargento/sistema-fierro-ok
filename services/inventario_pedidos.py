"""Núcleo preparado del ciclo pedido-inventario; no se conecta aún a canales."""

from collections import defaultdict
import json

from services.fechas import ahora_utc_naive


ESTADOS_CONFIGURACION = frozenset({"desactivado", "validacion", "activo"})
EVENTO_RESERVAR = "reservar"
EVENTO_LIBERAR = "liberar"
EVENTO_CONSUMIR = "consumir"


def clasificar_evento_pedido(estado):
    estado = str(estado or "").strip().lower()
    if estado in {"cancelado", "cancelada", "cancelled", "invalid"}:
        return EVENTO_LIBERAR
    if estado in {"despachado", "despachada", "shipped"}:
        return EVENTO_CONSUMIR
    return EVENTO_RESERVAR


def clave_evento_pedido(organizacion_id, pedido_id, tipo_evento):
    return f"org:{int(organizacion_id)}:pedido:{int(pedido_id)}:{tipo_evento}"


def agrupar_items_pedido(items):
    cantidades = defaultdict(int)
    for item in items or ():
        sku = str(getattr(item, "sku", "") or "").strip().upper()
        cantidad = int(getattr(item, "cantidad", 0) or 0)
        if sku and cantidad > 0:
            cantidades[sku] += cantidad
    return dict(cantidades)


def evaluar_preparacion_automatizacion(
    configuracion,
    *,
    sucursal,
    existencias,
    conteos,
):
    errores = []
    if sucursal is None or not bool(getattr(sucursal, "activa", False)):
        errores.append("Seleccioná una ubicación operativa activa.")
    controles = [
        existencia for existencia in existencias
        if bool(getattr(existencia, "control_activo", False))
    ]
    if not controles:
        errores.append("La ubicación necesita existencias con control activo.")
    if any(getattr(e, "item_inventario", None) is None for e in controles):
        errores.append("Todas las existencias deben estar vinculadas a un SKU estable.")
    conciliados = [
        conteo for conteo in conteos
        if str(getattr(conteo, "estado", "")) == "conciliado"
    ]
    if not conciliados:
        errores.append("Falta conciliar un inventario físico inicial de la ubicación.")
    if bool(getattr(configuracion, "permitir_stock_negativo", False)):
        errores.append("La automatización productiva no admite stock negativo.")
    return errores


def guardar_configuracion_automatizacion(
    organizacion,
    formulario,
    *,
    modelos,
    db_session,
):
    Configuracion = modelos["ConfiguracionInventarioPedidos"]
    Sucursal = modelos["SucursalOperativa"]
    Existencia = modelos["ExistenciaSucursal"]
    Conteo = modelos["ConteoInventario"]
    organizacion_id = int(organizacion.id)
    configuracion = Configuracion.query.filter_by(
        organizacion_id=organizacion_id,
    ).first()
    if configuracion is None:
        configuracion = Configuracion(organizacion_id=organizacion_id)
        db_session.add(configuracion)
    estado = str(formulario.get("estado") or "desactivado").strip().lower()
    if estado not in ESTADOS_CONFIGURACION:
        raise ValueError("El estado de automatización no es válido.")
    sucursal_id = int(formulario.get("sucursal_operativa_id") or 0)
    sucursal = Sucursal.query.filter_by(
        id=sucursal_id, organizacion_id=organizacion_id,
    ).first() if sucursal_id else None
    configuracion.sucursal_operativa_id = getattr(sucursal, "id", None)
    configuracion.reservar_al_ingresar = formulario.get("reservar_al_ingresar") == "1"
    configuracion.consumir_al_despachar = formulario.get("consumir_al_despachar") == "1"
    configuracion.liberar_al_cancelar = formulario.get("liberar_al_cancelar") == "1"
    configuracion.permitir_stock_negativo = False
    existencias = Existencia.query.filter_by(
        organizacion_id=organizacion_id,
        sucursal_operativa_id=getattr(sucursal, "id", 0),
    ).all() if sucursal else []
    conteos = Conteo.query.filter_by(
        organizacion_id=organizacion_id,
        sucursal_operativa_id=getattr(sucursal, "id", 0),
    ).all() if sucursal else []
    errores = evaluar_preparacion_automatizacion(
        configuracion, sucursal=sucursal, existencias=existencias, conteos=conteos,
    )
    if estado == "activo":
        if str(formulario.get("confirmacion") or "").strip().upper() != "AUTOMATIZAR":
            raise ValueError("Escribí AUTOMATIZAR para habilitar el ciclo productivo.")
        if errores:
            raise ValueError("No se puede activar: " + " ".join(errores))
    configuracion.estado = estado
    configuracion.fecha_ultima_validacion = ahora_utc_naive()
    configuracion.detalle_validacion = " ".join(errores) if errores else "Configuración lista."
    db_session.commit()
    return configuracion, errores


def automatizacion_puede_mutar(configuracion):
    """Única puerta para reservas/consumos futuros."""
    return str(getattr(configuracion, "estado", "")) == "activo"


def resolver_vinculo_pedido(pedido, vinculos):
    """Resuelve el tenant sin inferencias ambiguas entre cuentas comerciales."""
    canal = str(getattr(pedido, "canal", "") or "").strip().lower()
    if "mercado" in canal or getattr(pedido, "ml_cuenta_id", None):
        cuenta_id = int(getattr(pedido, "ml_cuenta_id", 0) or 0)
        if not cuenta_id:
            return None, "El pedido ML no conserva una cuenta de origen."
        candidatos = [
            vinculo for vinculo in vinculos
            if int(getattr(vinculo, "mercado_libre_cuenta_id", 0) or 0) == cuenta_id
        ]
    elif "tienda" in canal or getattr(pedido, "tn_order_id", None):
        cuenta_id = int(getattr(pedido, "tn_cuenta_id", 0) or 0)
        if not cuenta_id:
            return None, "El pedido de Tienda Nube todavía no conserva la cuenta de origen; no se puede aislar el tenant."
        candidatos = [
            vinculo for vinculo in vinculos
            if int(getattr(vinculo, "tienda_nube_cuenta_id", 0) or 0) == cuenta_id
        ]
    else:
        return None, "El pedido no tiene un canal empresarial resoluble."
    if len(candidatos) != 1:
        return None, "No existe un vínculo empresarial único para la cuenta del pedido."
    vinculo = candidatos[0]
    if str(getattr(vinculo, "estado", "")) != "activo":
        return None, "El vínculo empresarial del canal está desactivado."
    return vinculo, None


def construir_vista_previa_evento(
    pedido,
    tipo_evento,
    *,
    configuracion,
    vinculos,
    items_inventario,
    existencias,
):
    """Calcula efectos y bloqueos sin escribir cantidades ni reservas."""
    if tipo_evento not in {EVENTO_RESERVAR, EVENTO_LIBERAR, EVENTO_CONSUMIR}:
        raise ValueError("El evento de inventario no es válido.")
    bloqueos = []
    vinculo, error_vinculo = resolver_vinculo_pedido(pedido, vinculos)
    if error_vinculo:
        return {
            "pedido_id": 0,
            "organizacion_id": 0,
            "sucursal_operativa_id": 0,
            "canal": "no_resuelto",
            "tipo_evento": tipo_evento,
            "lineas": [],
            "bloqueos": [error_vinculo],
            "resultado": "bloqueado",
            "modo": "simulacion",
        }
    organizacion_id = int(getattr(vinculo, "organizacion_id", 0) or 0)
    sucursal_id = int(
        getattr(configuracion, "sucursal_operativa_id", 0)
        or getattr(vinculo, "sucursal_operativa_id", 0)
        or 0
    )
    if not sucursal_id:
        bloqueos.append("No hay una ubicación predeterminada para el pedido.")
    if str(getattr(configuracion, "estado", "desactivado")) != "activo":
        bloqueos.append("La automatización productiva está desactivada.")
    cantidades = agrupar_items_pedido(getattr(pedido, "items", ()))
    if not cantidades:
        bloqueos.append("El pedido no contiene SKU inventariables con cantidad válida.")
    items_por_sku = {
        str(getattr(item, "sku", "") or "").strip().upper(): item
        for item in items_inventario
        if int(getattr(item, "organizacion_id", 0) or 0) == organizacion_id
    }
    existencias_por_item = {
        int(getattr(existencia, "item_inventario_id", 0) or 0): existencia
        for existencia in existencias
        if int(getattr(existencia, "organizacion_id", 0) or 0) == organizacion_id
        and int(getattr(existencia, "sucursal_operativa_id", 0) or 0) == sucursal_id
    }
    lineas = []
    for sku, cantidad in cantidades.items():
        errores = []
        item = items_por_sku.get(sku)
        if item is None:
            errores.append("SKU no preparado")
            existencia = None
        else:
            if not bool(getattr(item, "activo", False)):
                errores.append("SKU desactivado")
            existencia = existencias_por_item.get(int(getattr(item, "id", 0) or 0))
            if existencia is None:
                errores.append("Sin existencia en la ubicación")
            elif not bool(getattr(existencia, "control_activo", False)):
                errores.append("Control de existencia desactivado")
        disponible = None
        reservado = None
        if existencia is not None:
            reservado = int(getattr(existencia, "stock_reservado", 0) or 0)
            disponible = (
                int(getattr(existencia, "stock_actual", 0) or 0)
                - reservado
                - int(getattr(existencia, "stock_bloqueado", 0) or 0)
            )
            if tipo_evento == EVENTO_RESERVAR and disponible < cantidad:
                errores.append("Stock disponible insuficiente")
            if tipo_evento in {EVENTO_LIBERAR, EVENTO_CONSUMIR} and reservado < cantidad:
                errores.append("Reserva insuficiente")
        lineas.append({
            "sku": sku,
            "cantidad": cantidad,
            "disponible": disponible,
            "reservado": reservado,
            "resultado": "bloqueado" if errores else "listo",
            "errores": errores,
        })
        bloqueos.extend(f"{sku}: {error}." for error in errores)
    return {
        "pedido_id": int(getattr(pedido, "id", 0) or 0),
        "organizacion_id": organizacion_id,
        "sucursal_operativa_id": sucursal_id,
        "canal": str(getattr(pedido, "canal", "") or ""),
        "tipo_evento": tipo_evento,
        "lineas": lineas,
        "bloqueos": list(dict.fromkeys(bloqueos)),
        "resultado": "bloqueado" if bloqueos else "listo",
        "modo": "simulacion",
    }


def simular_evento_pedido(
    organizacion,
    pedido_id,
    tipo_evento,
    *,
    modelos,
    db_session,
    usuario,
):
    """Registra una simulación idempotente; jamás invoca mutaciones de stock."""
    Pedido = modelos["Pedido"]
    Vinculo = modelos["VinculoCanalComercial"]
    Item = modelos["ItemInventario"]
    Existencia = modelos["ExistenciaSucursal"]
    Configuracion = modelos["ConfiguracionInventarioPedidos"]
    Evento = modelos["EventoInventarioPedido"]
    pedido = Pedido.query.get(int(pedido_id))
    if pedido is None:
        raise ValueError("No se encontró el pedido solicitado.")
    organizacion_id = int(organizacion.id)
    vinculos = Vinculo.query.filter_by(organizacion_id=organizacion_id).all()
    configuracion = Configuracion.query.filter_by(organizacion_id=organizacion_id).first()
    vista = construir_vista_previa_evento(
        pedido,
        tipo_evento,
        configuracion=configuracion,
        vinculos=vinculos,
        items_inventario=Item.query.filter_by(organizacion_id=organizacion_id).all(),
        existencias=Existencia.query.filter_by(organizacion_id=organizacion_id).all(),
    )
    if vista["organizacion_id"] != organizacion_id:
        raise ValueError("No se pudo validar el pedido dentro de la organización activa.")
    clave = "sim:" + clave_evento_pedido(organizacion_id, pedido.id, tipo_evento)
    evento = Evento.query.filter_by(
        organizacion_id=organizacion_id,
        clave_idempotencia=clave,
    ).first()
    if evento is None:
        evento = Evento(
            organizacion_id=organizacion_id,
            pedido_id=pedido.id,
            tipo_evento=tipo_evento,
            clave_idempotencia=clave,
        )
        db_session.add(evento)
    vista["usuario"] = str(usuario or "admin")
    evento.estado = "simulado_" + vista["resultado"]
    evento.detalle = json.dumps(vista, ensure_ascii=False, sort_keys=True)
    evento.fecha_procesamiento = ahora_utc_naive()
    db_session.commit()
    return vista, evento
