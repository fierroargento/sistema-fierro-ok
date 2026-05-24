from datetime import datetime, UTC
from domain.estados import Estado


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
            estado=Estado.CARGANDO_PEDIDO,
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

    pedido.mail = pedido.mail or ""
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
            Estado.ENTREGADO,
            Estado.FINALIZADO,
            Estado.CANCELADO,
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




def ml_limpiar_pedidos_ml_no_operables_existentes_service(
    Pedido,
    ml_obtener_order,
    ml_obtener_shipment,
    ml_order_esta_entregado,
    ml_estado_order,
    ml_estado_shipment,
    ml_order_debe_omitirse,
    ml_borrar_pedido_importado_si_corresponde,
):
    pedidos = (
        Pedido.query
        .filter_by(
            canal="Mercado Libre",
            origen="mercadolibre",
            estado=Estado.CARGANDO_PEDIDO,
        )
        .order_by(Pedido.id.asc())
        .all()
    )

    eliminados = 0
    detalles = []

    for pedido in pedidos:
        order_id = str(
            pedido.id_venta or ""
        ).strip()

        if not order_id:
            continue

        order = ml_obtener_order(
            order_id
        )

        if not order:
            continue

        shipment = ml_obtener_shipment(
            (order.get("shipping") or {}).get("id")
        )

        if ml_order_esta_entregado(
            order,
            shipment,
        ):
            pedido.ml_order_status = (
                ml_estado_order(order)
                or pedido.ml_order_status
            )

            estado_shipping = ml_estado_shipment(
                order,
                shipment,
            )

            if estado_shipping:
                pedido.ml_shipping_status = estado_shipping

            ahora = datetime.now(UTC)

            pedido.estado = Estado.ENTREGADO
            pedido.fecha_entregado = (
                pedido.fecha_entregado
                or ahora
            )

            pedido.ultima_sync_ml = ahora

            detalles.append(
                f"{order_id}: ML informó entregado; pedido actualizado a Entregado"
            )

            continue

        omitir, motivo = ml_order_debe_omitirse(
            order,
            shipment,
        )

        if (
            omitir
            and ml_borrar_pedido_importado_si_corresponde(pedido)
        ):
            eliminados += 1
            detalles.append(
                f"{order_id}: eliminado ({motivo})"
            )

    return eliminados, detalles

def ml_procesar_orders_sync_service(
    orders,
    ml_upsert_pedido_desde_order,
):
    creados = 0
    actualizados = 0
    omitidos = 0
    errores = []

    mercado_envios_sin_etiqueta = 0
    mercado_envios_sin_etiqueta_ids = []

    for order in orders:

        order_id = str(
            (order or {}).get("id")
            or ""
        ).strip() or "sin_id"

        try:
            pedido, creado, motivo_omision = (
                ml_upsert_pedido_desde_order(
                    order
                )
            )

            if not pedido:
                omitidos += 1

                if (
                    motivo_omision
                    and "__ML_ME_SIN_ETIQUETA__"
                    in motivo_omision
                ):
                    mercado_envios_sin_etiqueta += 1

                    mercado_envios_sin_etiqueta_ids.append(
                        order_id
                    )

                    errores.append(
                        f"{order_id}: omitido "
                        f"(Mercado Envíos sin etiqueta)"
                    )

                elif motivo_omision:
                    errores.append(
                        f"{order_id}: omitido "
                        f"({motivo_omision})"
                    )

                continue

            if creado:
                creados += 1
            else:
                actualizados += 1

        except Exception as e:
            omitidos += 1
            errores.append(
                f"{order_id}: {e}"
            )

    return {
        "creados": creados,
        "actualizados": actualizados,
        "omitidos": omitidos,
        "errores": errores,
        "me_sin_etiqueta": mercado_envios_sin_etiqueta,
        "me_sin_etiqueta_ids": (
            mercado_envios_sin_etiqueta_ids
        ),
    }




def ml_actualizar_resumen_sync_service(
    cuenta,
    orders,
    creados,
    actualizados,
    omitidos,
    eliminados_existentes,
    mensajes_pendientes,
    claims_marcados,
    errores,
    mercado_envios_sin_etiqueta,
    mercado_envios_sin_etiqueta_ids,
    session,
):
    ahora = datetime.now(UTC)

    cuenta.last_sync_at = ahora

    cuenta.last_sync_status = (
        "ok"
        if not errores
        else "parcial"
    )

    detalle = (
        f"Pedidos leídos: {len(orders)} "
        f"| Nuevos: {creados} "
        f"| Actualizados: {actualizados} "
        f"| Omitidos: {omitidos} "
        f"| Eliminados no operables: {eliminados_existentes} "
        f"| Mensajes ML pendientes: {mensajes_pendientes} "
        f"| Reclamos ML detectados: {claims_marcados}"
    )

    if errores:
        detalle += (
            " | Detalle: "
            + " ; ".join(errores[:5])
        )

    cuenta.last_sync_detail = detalle

    session["ml_me_sin_etiqueta_count"] = (
        mercado_envios_sin_etiqueta
    )

    session["ml_me_sin_etiqueta_ids"] = (
        mercado_envios_sin_etiqueta_ids[:10]
    )

    return {
        "leidos": len(orders),
        "creados": creados,
        "actualizados": actualizados,
        "omitidos": omitidos,
        "eliminados": eliminados_existentes,
        "mensajes_pendientes": mensajes_pendientes,
        "claims_marcados": claims_marcados,
        "errores": errores,
        "me_sin_etiqueta": mercado_envios_sin_etiqueta,
    }