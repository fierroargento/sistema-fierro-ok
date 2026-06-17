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
            estado=Estado.CARGANDO,
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
            estado=Estado.CARGANDO,
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


def ml_aplicar_datos_envio_service(
    pedido,
    order,
    shipment,
    ml_mapear_tipo_fn,
    ml_mapear_tipo_entrega_fn,
    aplicar_default_tipo_entrega_fn,
    es_ml_acordas_via_cargo_fn,
    etiqueta_archivo_local_disponible_fn,
    ml_guardar_etiqueta_pdf_fn,
):
    """
    Aplica datos logisticos de Mercado Libre al pedido.

    APB:
    - No conoce Flask, db ni app.config.
    - Mantiene la mutacion del pedido en una regla testeable.
    - Recibe helpers externos inyectados desde app.py.
    """
    import os

    order = order or {}
    shipment = shipment or {}

    shipping = order.get("shipping") or {}
    receiver_address = shipment.get("receiver_address") or {}
    city = receiver_address.get("city") or {}
    state = receiver_address.get("state") or {}

    pedido.ml_shipping_id = str(
        shipping.get("id")
        or shipment.get("id")
        or pedido.ml_shipping_id
        or ""
    ).strip()

    pedido.ml_logistic_type = str(
        shipment.get("logistic_type")
        or shipping.get("logistic_type")
        or pedido.ml_logistic_type
        or ""
    ).strip()

    pedido.ml_shipping_mode = str(
        shipment.get("mode")
        or shipping.get("mode")
        or pedido.ml_shipping_mode
        or ""
    ).strip()

    pedido.ml_tipo = ml_mapear_tipo_fn(order, shipment)
    pedido.tipo_entrega = ml_mapear_tipo_entrega_fn(order, shipment)

    pedido.seguimiento = (
        shipment.get("tracking_number")
        or shipment.get("tracking_method")
        or pedido.seguimiento
    )

    if pedido.ml_tipo == "Mercado Envíos":
        pedido.empresa_envio = "Mercado Envíos"

    pedido.direccion = receiver_address.get("address_line") or pedido.direccion
    pedido.codigo_postal = receiver_address.get("zip_code") or pedido.codigo_postal
    pedido.localidad = city.get("name") or pedido.localidad
    pedido.provincia = state.get("name") or pedido.provincia
    pedido.sucursal_nombre = receiver_address.get("agency_name") or pedido.sucursal_nombre

    aplicar_default_tipo_entrega_fn(pedido)

    if pedido.sucursal_nombre and es_ml_acordas_via_cargo_fn(pedido):
        pedido.tipo_entrega = "Sucursal"

    pedido.ml_shipping_status = (
        shipment.get("status")
        or shipping.get("status")
        or pedido.ml_shipping_status
    )

    if pedido.ml_tipo == "Mercado Envíos" and pedido.ml_shipping_id:
        if (
            not pedido.etiqueta_archivo
            or not etiqueta_archivo_local_disponible_fn(pedido.etiqueta_archivo)
        ):
            nombre_pdf = ml_guardar_etiqueta_pdf_fn(pedido.ml_shipping_id)
            if nombre_pdf:
                pedido.etiqueta_archivo = os.path.basename(str(nombre_pdf))

    return pedido


def ml_datos_apb_pedido_service(
    pedido,
    es_ml_acordas_entrega_fn,
    parece_nickname_ml_fn,
    despacho_completo_fn,
):
    faltantes = []

    if not pedido:
        return faltantes

    if es_ml_acordas_entrega_fn(pedido):
        cliente = getattr(pedido, "cliente", "")
        ml_buyer_nickname = getattr(pedido, "ml_buyer_nickname", "")
        ml_billing_nombre = getattr(pedido, "ml_billing_nombre", "")
        dni = getattr(pedido, "dni", "")
        ml_billing_documento = getattr(pedido, "ml_billing_documento", "")
        telefono = getattr(pedido, "telefono", "")

        if parece_nickname_ml_fn(cliente, ml_buyer_nickname) and not (ml_billing_nombre or "").strip():
            faltantes.append("nombre real")

        if not (dni or "").strip() and not (ml_billing_documento or "").strip():
            faltantes.append("DNI/CUIT")

        if not (telefono or "").strip():
            faltantes.append("tel\u00e9fono")

        if not despacho_completo_fn(pedido):
            faltantes.append("datos de entrega")

    return faltantes


def ml_aplicar_apb_en_pedido_service(
    pedido,
    order,
    shipment,
    billing_info,
    ml_nombre_cliente_fn,
    ml_extraer_nombre_billing_fn,
    ml_extraer_documento_billing_fn,
    ml_extraer_direccion_billing_fn,
    ml_extraer_telefono_fn,
    ml_buyer_tiene_nombre_real_fn,
    parece_nickname_ml_fn,
    ml_datos_apb_pedido_fn,
    generar_mensaje_contacto_ml_fn,
):
    order = order or {}
    shipment = shipment or {}
    billing_info = billing_info or {}

    buyer = order.get("buyer") or {}

    pedido.ml_buyer_id = str(
        buyer.get("id")
        or getattr(pedido, "ml_buyer_id", "")
        or ""
    ).strip()

    pedido.ml_buyer_nickname = str(
        buyer.get("nickname")
        or getattr(pedido, "ml_buyer_nickname", "")
        or ""
    ).strip()

    nombre_ml = ml_nombre_cliente_fn(order, shipment)
    nombre_billing = ml_extraer_nombre_billing_fn(billing_info)
    documento_billing = ml_extraer_documento_billing_fn(billing_info)
    direccion_billing = ml_extraer_direccion_billing_fn(billing_info)
    telefono_ml = ml_extraer_telefono_fn(order, shipment)

    pedido.ml_nombre_real = bool(
        ml_buyer_tiene_nombre_real_fn(order)
        or (
            nombre_ml
            and not parece_nickname_ml_fn(
                nombre_ml,
                getattr(pedido, "ml_buyer_nickname", ""),
            )
        )
    )

    pedido.ml_datos_fiscales_ok = bool(
        documento_billing
        or nombre_billing
    )

    pedido.ml_billing_nombre = (
        nombre_billing
        or getattr(pedido, "ml_billing_nombre", "")
    )
    pedido.ml_billing_documento = (
        documento_billing
        or getattr(pedido, "ml_billing_documento", "")
    )
    pedido.ml_billing_direccion = (
        direccion_billing
        or getattr(pedido, "ml_billing_direccion", "")
    )

    if nombre_ml and not parece_nickname_ml_fn(
        nombre_ml,
        getattr(pedido, "ml_buyer_nickname", ""),
    ):
        pedido.cliente = nombre_ml
    elif nombre_billing and parece_nickname_ml_fn(
        getattr(pedido, "cliente", ""),
        getattr(pedido, "ml_buyer_nickname", ""),
    ):
        pedido.cliente = nombre_billing

    if documento_billing and not (getattr(pedido, "dni", "") or "").strip():
        pedido.dni = documento_billing

    if telefono_ml and not (getattr(pedido, "telefono", "") or "").strip():
        pedido.telefono = telefono_ml

    faltantes = ml_datos_apb_pedido_fn(pedido)
    pedido.ml_campos_faltantes = ", ".join(faltantes)
    pedido.ml_mensaje_contacto = (
        generar_mensaje_contacto_ml_fn(pedido)
        if faltantes
        else ""
    )

    return pedido

