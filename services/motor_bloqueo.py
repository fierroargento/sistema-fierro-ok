from services.pedidos_estado import (
    usa_flujo_acordas_entrega,
    despacho_completo,
    hay_autorizado,
    es_via_cargo,
)


def validar_datos_entrega(pedido):
    errores = []

    requiere_datos_envio = True

    if usa_flujo_acordas_entrega(pedido) and not despacho_completo(pedido):
        requiere_datos_envio = False

    if requiere_datos_envio and pedido.empresa_envio:
        if not pedido.tipo_entrega:
            errores.append("Falta tipo de entrega.")

        if pedido.tipo_entrega == "Domicilio":
            if not pedido.direccion or not pedido.localidad or not pedido.provincia:
                errores.append("Faltan datos domicilio.")
            if not pedido.codigo_postal:
                errores.append("Falta CP.")

        if pedido.tipo_entrega == "Sucursal":
            if not pedido.sucursal_nombre:
                errores.append("Falta nombre de sucursal.")

            if (
                not pedido.direccion
                or not pedido.localidad
                or not pedido.provincia
            ):
                errores.append("Faltan datos sucursal.")

            if hay_autorizado(pedido):
                if not pedido.autorizado_nombre:
                    errores.append("Falta nombre del autorizado.")
                if not pedido.autorizado_dni:
                    errores.append("Falta DNI del autorizado.")
                if not pedido.autorizado_telefono:
                    errores.append("Falta teléfono del autorizado.")

    return errores

def validar_datos_ml(pedido, parece_nickname_ml):
    errores = []

    if pedido.canal == "Mercado Libre":
        if not pedido.ml_tipo:
            errores.append("Falta tipo de envío ML.")

        elif pedido.ml_tipo == "Mercado Envíos":
            if not pedido.seguimiento:
                errores.append("Falta seguimiento ML.")
            if not pedido.etiqueta_archivo:
                errores.append("Falta adjuntar etiqueta.")

        elif pedido.ml_tipo == "Acordás la Entrega":
            if parece_nickname_ml(pedido.cliente, pedido.ml_buyer_nickname) and not (pedido.ml_billing_nombre or "").strip():
                errores.append("Falta nombre real del cliente.")
            if not (pedido.dni or "").strip() and not (pedido.ml_billing_documento or "").strip():
                errores.append("Falta DNI/CUIT del cliente.")
            if not (pedido.telefono or "").strip():
                errores.append("Falta teléfono del cliente.")

    return errores

def validar_transportes(pedido, es_tnube):
    errores = []

    if pedido.empresa_envio in ["Andreani", "Correo Argentino"]:
        if not pedido.seguimiento:
            errores.append("Falta número de seguimiento.")
        if not pedido.etiqueta_archivo:
            errores.append("Falta adjuntar etiqueta.")

    if es_tnube(pedido) and not pedido.empresa_envio:
        errores.append("Falta transporte.")

    return errores

def validar_datos_basicos(pedido):
    errores = []

    if not pedido.cliente:
        errores.append("Falta cliente.")

    if not pedido.canal:
        errores.append("Falta canal.")

    if not pedido.items:
        errores.append("No hay productos cargados.")

    return errores

def cantidad_pp6040_pedido(pedido):
    """
    Cantidad total de unidades PP6040 en el pedido.

    APB:
    - La regla se centraliza en domain/productos.py.
    - Cuenta solo por SKU.
    - No mira descripción ni observaciones.
    - PA9060H no suma como PP6040.
    """
    if not pedido:
        return 0

    from domain.productos import es_sku_pp6040

    total = 0
    for item in (getattr(pedido, "items", None) or []):
        if es_sku_pp6040(getattr(item, "sku", "")):
            try:
                total += int(getattr(item, "cantidad", 0) or 0)
            except Exception:
                pass

    return total


def via_cargo_no_permitido_para_pp6040(pedido):
    """PP6040 no puede ir por Vía Cargo salvo pedidos de 3 unidades o más."""
    if not pedido or not es_via_cargo(getattr(pedido, "empresa_envio", None)):
        return False

    cantidad = cantidad_pp6040_pedido(pedido)
    return cantidad > 0 and cantidad <= 2


def validar_regla_via_cargo_pp6040(pedido):
    if via_cargo_no_permitido_para_pp6040(pedido):
        cantidad = cantidad_pp6040_pedido(pedido)
        return f"PP6040 no puede enviarse por Vía Cargo con {cantidad} unidad(es). Vía Cargo solo queda habilitado para PP6040 cuando el pedido tiene más de 2 unidades."
    return None

def validar_transporte_obligatorio(pedido, usa_flujo_etiqueta_directa):
    errores = []

    requiere_datos_envio = True

    if usa_flujo_acordas_entrega(pedido) and not despacho_completo(pedido):
        requiere_datos_envio = False

    if (
        requiere_datos_envio
        and not pedido.empresa_envio
        and not usa_flujo_etiqueta_directa(pedido)
    ):
        errores.append("Falta transporte.")

    return errores    