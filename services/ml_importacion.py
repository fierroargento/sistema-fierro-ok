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

from datetime import datetime, UTC


def ml_preparar_pedido_base_importacion_service(
    order,
    shipment,
    id_operativo_ml,
    etiqueta_ml_preparada,
    Pedido,
    db,
    ml_nombre_cliente,
    ml_es_mercado_envios_order,
    ml_pedido_existente_operativo,
    ml_aplicar_datos_envio,
    ml_aplicar_apb_en_pedido,
    billing_info=None,
):
    pedido = ml_pedido_existente_operativo(
        order,
        shipment,
    )

    creado = pedido is None

    if creado:
        pedido = Pedido(
            cliente=ml_nombre_cliente(
                order,
                shipment,
            ),
            canal="Mercado Libre",
            id_venta=id_operativo_ml,
            estado="Cargando Pedido",
            origen="mercadolibre",
        )

        db.session.add(pedido)

    pedido.origen = "mercadolibre"
    pedido.canal = "Mercado Libre"

    if not pedido.id_venta:
        pedido.id_venta = id_operativo_ml

    if (
        ml_es_mercado_envios_order(order, shipment)
        and id_operativo_ml
        and pedido.id_venta != id_operativo_ml
    ):
        pedido.id_venta = id_operativo_ml

    pedido.mail = pedido.mail or "expedicionfierro@gmail.com"
    pedido.telefono = pedido.telefono or ""
    pedido.observaciones = (
        pedido.observaciones or ""
    ).strip()

    pedido.ml_pack_id = (
        str((order or {}).get("pack_id") or "").strip()
        or pedido.ml_pack_id
    )

    pedido.ml_order_status = (
        (order or {}).get("status")
        or pedido.ml_order_status
    )

    pedido.ultima_sync_ml = datetime.now(UTC)

    if etiqueta_ml_preparada:
        pedido.etiqueta_archivo = etiqueta_ml_preparada

    ml_aplicar_datos_envio(
        pedido,
        order,
        shipment,
    )

    ml_aplicar_apb_en_pedido(
        pedido,
        order,
        shipment,
        billing_info,
    )

    return pedido, creado

def ml_intentar_contacto_inicial_acordas_service(
    pedido,
    creado,
    es_ml_acordas_entrega,
    ml_auto_enviar_contacto_inicial_acordas,
):
    """
    APB:
    Al crear un pedido nuevo de Mercado Libre / Acordás la Entrega,
    intenta enviar automáticamente el primer mensaje de contacto.
    Si ML lo rechaza, no rompe la importación.
    """

    estados_ml_bloqueados = {
        "closed",
        "cancelled",
        "invalid",
        "delivered",
    }

    ml_order_status_actual = str(
        getattr(pedido, "ml_order_status", "") or ""
    ).lower().strip()

    if (
        creado
        and es_ml_acordas_entrega(pedido)
        and not getattr(pedido, "contacto_iniciado", False)
        and ml_order_status_actual not in estados_ml_bloqueados
        and pedido.estado not in [
            "Entregado",
            "Finalizado",
            "Cancelado",
        ]
    ):
        enviado_auto, motivo_auto = ml_auto_enviar_contacto_inicial_acordas(
            pedido
        )

        if not enviado_auto:
            print(
                f"[ML-AUTO-CONTACTO] Pedido #{getattr(pedido, 'id', '')} "
                f"queda pendiente. Motivo: {motivo_auto}"
            )

        return enviado_auto, motivo_auto

    return False, ""