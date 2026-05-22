def ml_prevalidar_importacion_order_service(
    order,
    shipment,
    ml_pedido_esta_ignorado,
    ml_order_esta_entregado,
    ml_pedido_existente_operativo,
    ml_registrar_order_ignorado,
    ml_marcar_pedido_finalizado_por_entrega,
    ml_order_debe_omitirse,
    ml_borrar_pedido_importado_si_corresponde,
    ml_es_mercado_envios_order,
    ml_envio_ya_despachado,
    ml_preparar_etiqueta_mercado_envios,
):
    order_id = str(
        (order or {}).get("id") or ""
    ).strip()

    if ml_pedido_esta_ignorado(order_id):
        return {
            "pedido": None,
            "continuar": False,
            "creado": False,
            "motivo": "pedido eliminado manualmente en Fierro",
            "shipment": shipment,
            "etiqueta_ml_preparada": "",
        }

    # APB ML:
    # si Mercado Libre ya informa Entregado:
    # - Si NO existe en Fierro, se omite como histórico.
    # - Si SÍ existe, se actualiza automáticamente a Finalizado.

    if ml_order_esta_entregado(order, shipment):

        pedido = ml_pedido_existente_operativo(
            order,
            shipment,
        )

        if pedido is None:

            ml_registrar_order_ignorado(
                order_id,
                "ML entregado/histórico omitido: no existía en Fierro",
            )

            return {
                "pedido": None,
                "continuar": False,
                "creado": False,
                "motivo": "ML entregado/histórico omitido: no existía en Fierro",
                "shipment": shipment,
                "etiqueta_ml_preparada": "",
            }

        pedido = ml_marcar_pedido_finalizado_por_entrega(
            pedido,
            order,
            shipment,
        )

        return {
            "pedido": pedido,
            "continuar": False,
            "creado": False,
            "motivo": "ML informó entregado; pedido actualizado automáticamente a Finalizado",
            "shipment": shipment,
            "etiqueta_ml_preparada": "",
        }

    omitir, motivo_omision = ml_order_debe_omitirse(
        order,
        shipment,
    )

    if omitir:

        pedido_existente = ml_pedido_existente_operativo(
            order,
            shipment,
        )

        if ml_borrar_pedido_importado_si_corresponde(
            pedido_existente
        ):

            return {
                "pedido": None,
                "continuar": False,
                "creado": False,
                "motivo": f"{motivo_omision} - pedido importado eliminado",
                "shipment": shipment,
                "etiqueta_ml_preparada": "",
            }

        return {
            "pedido": None,
            "continuar": False,
            "creado": False,
            "motivo": motivo_omision,
            "shipment": shipment,
            "etiqueta_ml_preparada": "",
        }

    etiqueta_ml_preparada = ""

    if ml_es_mercado_envios_order(
        order,
        shipment,
    ):

        if ml_envio_ya_despachado(
            order,
            shipment,
        ):

            pedido_existente = ml_pedido_existente_operativo(
                order,
                shipment,
            )

            if ml_borrar_pedido_importado_si_corresponde(
                pedido_existente
            ):

                return {
                    "pedido": None,
                    "continuar": False,
                    "creado": False,
                    "motivo": "Mercado Envíos ya enviado - pedido importado eliminado",
                    "shipment": shipment,
                    "etiqueta_ml_preparada": "",
                }

            return {
                "pedido": None,
                "continuar": False,
                "creado": False,
                "motivo": "Mercado Envíos ya enviado",
                "shipment": shipment,
                "etiqueta_ml_preparada": "",
            }

        etiqueta_ml_preparada = (
            ml_preparar_etiqueta_mercado_envios(
                order,
                shipment,
            )
        )

        if not etiqueta_ml_preparada:

            pedido_existente = ml_pedido_existente_operativo(
                order,
                shipment,
            )

            if ml_borrar_pedido_importado_si_corresponde(
                pedido_existente
            ):

                return {
                    "pedido": None,
                    "continuar": False,
                    "creado": False,
                    "motivo": "__ML_ME_SIN_ETIQUETA__ - pedido importado eliminado",
                    "shipment": shipment,
                    "etiqueta_ml_preparada": "",
                }

            return {
                "pedido": None,
                "continuar": False,
                "creado": False,
                "motivo": "__ML_ME_SIN_ETIQUETA__",
                "shipment": shipment,
                "etiqueta_ml_preparada": "",
            }

    return {
        "pedido": None,
        "continuar": True,
        "creado": False,
        "motivo": "",
        "shipment": shipment,
        "etiqueta_ml_preparada": etiqueta_ml_preparada,
    }