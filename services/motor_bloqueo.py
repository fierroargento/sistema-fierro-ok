from services.pedidos_estado import (
    usa_flujo_acordas_entrega,
    despacho_completo,
    hay_autorizado,
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