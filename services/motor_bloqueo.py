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