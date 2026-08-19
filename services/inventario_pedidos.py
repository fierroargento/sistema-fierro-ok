"""Núcleo preparado del ciclo pedido-inventario; no se conecta aún a canales."""

from collections import defaultdict

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
