"""
Job automático ML mensajes.

Extraído desde app.py sin cambiar lógica.
"""

def ejecutar_job_ml_mensajes(app, db):
    """Procesa mensajes pendientes de ML Acordás cada 5 minutos."""

    try:
        with app.app_context():
            from app import (
                Pedido,
                MercadoLibreCuenta,
                ia_escalar_si_timeout_operativo,
                ml_obtener_mensajes_pack_para_ia,
                ia_analizar_ultimo_mensaje_pedido,
            )

            cuenta = MercadoLibreCuenta.query.first()
            seller_id = str((cuenta.user_id_ml if cuenta else "") or "").strip()

            # APB anti-acoso: si el bot ML habló y el comprador no respondió
            # durante 2 horas operativas, escala al operador. No insiste.
            pedidos_esperando = (
                Pedido.query
                .filter(Pedido.canal == "Mercado Libre")
                .filter(Pedido.ia_esperando_respuesta == True)
                .filter(Pedido.estado.notin_(["Despachado", "Entregado", "Finalizado", "Cancelado"]))
                .all()
            )

            for p_wait in pedidos_esperando:
                # APB CANAL: si WhatsApp ya está activo, el timeout lo gobierna WA, no ML.
                if str(getattr(p_wait, "wa_estado", "") or "").strip():
                    continue

                ia_escalar_si_timeout_operativo(
                    p_wait,
                    canal="mercadolibre"
                )

            pedidos = (
                Pedido.query
                .filter(Pedido.canal == "Mercado Libre")
                .filter(Pedido.ml_tipo == "Acordás la Entrega")
                .filter(Pedido.ml_mensajes_pendientes == True)
                .filter(Pedido.estado.notin_(["Despachado", "Entregado", "Finalizado", "Cancelado"]))
                .all()
            )

            for pedido in pedidos:
                try:
                    # APB CANAL: si WhatsApp ya tomó la posta, ML queda pasivo.
                    if str(getattr(pedido, "wa_estado", "") or "").strip():
                        continue

                    ids_chat = []

                    for posible in [
                        getattr(pedido, "ml_pack_id", None),
                        getattr(pedido, "id_venta", None),
                    ]:
                        posible = str(posible or "").strip()

                        if posible and posible not in ids_chat:
                            ids_chat.append(posible)

                    mensajes = []

                    for id_chat in ids_chat:
                        mensajes = ml_obtener_mensajes_pack_para_ia(
                            id_chat,
                            seller_id=seller_id
                        )

                        if mensajes:
                            break

                    if mensajes:
                        resultado = ia_analizar_ultimo_mensaje_pedido(
                            pedido,
                            mensajes,
                            seller_id=seller_id,
                            forzar=False
                        )

                        if resultado:
                            db.session.commit()

                except Exception as e:
                    print(
                        f"[SCHEDULER ML] Error procesando pedido #{pedido.id}:",
                        e
                    )

                    try:
                        db.session.rollback()
                    except Exception:
                        pass

    except Exception as e:
        print("[SCHEDULER ML] Error general:", e)

        try:
            db.session.rollback()
        except Exception:
            pass

    finally:
        try:
            db.session.remove()
        except Exception:
            pass