"""
services/correo_argentino_operacion.py

Capa operativa para usar resultados de MiCorreo/Correo dentro del pedido.

No consulta APIs.
No crea envíos.
No paga.
No imprime etiquetas.

Solo normaliza decisiones para que el sistema pueda guardar/mostrar:
- modalidad elegida
- costo sucursal
- costo domicilio
- servicio
- motivo
"""

TRANSPORTE_CORREO = "Correo Argentino"


def _to_float(valor, default=0.0):
    try:
        if valor is None or valor == "":
            return default
        return float(valor)
    except Exception:
        return default


def _cotizacion_disponible(cotizacion):
    cotizacion = cotizacion or {}
    return bool(cotizacion.get("disponible") and cotizacion.get("precio") is not None)


def extraer_resumen_cotizacion(resultado):
    """Extrae datos útiles del resultado de selector.evaluar_decision_correo_pp6040()."""
    resultado = resultado or {}
    sucursal = resultado.get("sucursal") or {}
    domicilio = resultado.get("domicilio") or {}
    decision = str(resultado.get("decision") or "").strip().lower()

    precio_sucursal = _to_float(sucursal.get("precio"))
    precio_domicilio = _to_float(domicilio.get("precio"))

    if decision == "domicilio":
        precio_elegido = precio_domicilio
        tipo_entrega = "Domicilio"
        servicio = domicilio.get("servicio") or domicilio.get("tipo") or ""
    elif decision == "sucursal":
        precio_elegido = precio_sucursal
        tipo_entrega = "Sucursal"
        servicio = sucursal.get("servicio") or sucursal.get("tipo") or ""
    else:
        precio_elegido = 0.0
        tipo_entrega = ""
        servicio = ""

    return {
        "ok": decision in {"sucursal", "domicilio"},
        "transporte": TRANSPORTE_CORREO,
        "decision": decision,
        "tipo_entrega": tipo_entrega,
        "precio_elegido": precio_elegido,
        "precio_sucursal": precio_sucursal,
        "precio_domicilio": precio_domicilio,
        "sucursal_disponible": _cotizacion_disponible(sucursal),
        "domicilio_disponible": _cotizacion_disponible(domicilio),
        "servicio": servicio,
        "motivo": resultado.get("motivo") or resultado.get("error") or "",
        "cp_destino": resultado.get("cp_destino") or "",
        "raw": resultado,
    }


def aplicar_resumen_cotizacion_a_pedido(pedido, resumen):
    """Aplica el resumen a un objeto pedido compatible.

    No hace commit. La transacción queda a cargo del llamador.
    """
    resumen = resumen or {}

    if not resumen.get("ok"):
        return False, resumen.get("motivo") or "Cotización Correo no aplicable"

    pedido.empresa_envio = TRANSPORTE_CORREO
    pedido.tipo_entrega = resumen.get("tipo_entrega") or ""

    if hasattr(pedido, "costo_envio"):
        pedido.costo_envio = _to_float(resumen.get("precio_elegido"))

    if hasattr(pedido, "costo_envio_sucursal"):
        pedido.costo_envio_sucursal = _to_float(resumen.get("precio_sucursal"))

    if hasattr(pedido, "costo_envio_domicilio"):
        pedido.costo_envio_domicilio = _to_float(resumen.get("precio_domicilio"))

    if hasattr(pedido, "ia_resumen"):
        anterior = (getattr(pedido, "ia_resumen", "") or "").strip()
        detalle = (
            f"Correo Argentino evaluado: {resumen.get('tipo_entrega')}. "
            f"{resumen.get('motivo') or ''}"
        ).strip()
        pedido.ia_resumen = f"{anterior} | {detalle}".strip(" |")

    return True, f"Correo Argentino aplicado ({pedido.tipo_entrega})"


def armar_lineas_cotizacion_cliente(resumen):
    """Arma líneas internas para operador. No incluye promesa comercial al cliente."""
    resumen = resumen or {}
    lineas = []

    if resumen.get("precio_sucursal"):
        lineas.append(
            f"Sucursal: ${resumen['precio_sucursal']:.0f}"
        )

    if resumen.get("precio_domicilio"):
        lineas.append(
            f"Domicilio: ${resumen['precio_domicilio']:.0f}"
        )

    if resumen.get("servicio"):
        lineas.append(f"Servicio elegido: {resumen['servicio']}")

    if resumen.get("motivo"):
        lineas.append(f"Motivo: {resumen['motivo']}")

    return lineas
