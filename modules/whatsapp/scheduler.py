"""
modules/whatsapp/scheduler.py
──────────────────────────────
Scheduler central APB.

Se ejecuta periódicamente desde modules.whatsapp.activar(app), enganchado a before_request.
No abre threads ni procesos extra, para no complicar Render.
"""

from datetime import datetime, timedelta
from threading import Lock

_scheduler_lock = Lock()


def _cerrar_sesion_db_segura(rollback=False):
    """Limpieza defensiva de SQLAlchemy para schedulers/background jobs.

    En Render/Postgres puede cortarse SSL; si queda una transacción inválida,
    SQLAlchemy exige rollback antes de reutilizar la conexión. Este helper evita
    que un error de scheduler rompa requests normales.
    """
    try:
        from app import db
        if rollback:
            try:
                db.session.rollback()
            except Exception:
                pass
        try:
            db.session.remove()
        except Exception:
            pass
    except Exception:
        pass


from .config import (
    TIMER_PRIMER_RECORDATORIO,
    TIMER_SEGUNDO_RECORDATORIO,
    TIMER_CROSS_SELL_SIGUIENTE,
    TRACKING_INTERVALO_MINUTOS,
    modulo_activo,
)
from .flows import (
    wa_enviar_recordatorio_1,
    wa_enviar_recordatorio_2,
    _guardar_estado_wa,
)


def ejecutar_timers():
    """Punto único de scheduler.

    Protegido contra ejecuciones simultáneas: el módulo puede dispararse desde
    APScheduler y también desde el hook liviano de requests. Si se solapan, se
    saltea una vuelta para no compartir sesión DB ni duplicar consultas externas.
    """
    if not _scheduler_lock.acquire(blocking=False):
        print("[WA SCHEDULER] Tick omitido: ya hay un scheduler corriendo")
        return

    hubo_error = False
    try:
        ejecutar_timers_whatsapp()
        ejecutar_tracking_automatico()
    except Exception as e:
        hubo_error = True
        print("[WA SCHEDULER] Error general ejecutar_timers:", e)
    finally:
        _cerrar_sesion_db_segura(rollback=hubo_error)
        _scheduler_lock.release()


def ejecutar_timers_whatsapp():
    if not modulo_activo():
        return
    try:
        from app import db, Pedido
        ahora = datetime.utcnow()
        pedidos = (
            Pedido.query
            .filter(Pedido.wa_estado.isnot(None))
            .filter(Pedido.wa_estado != "")
            .filter(Pedido.wa_ultimo_contacto.isnot(None))
            .filter(Pedido.estado.notin_(["Entregado", "Finalizado", "Cancelado"]))
            .all()
        )
        for pedido in pedidos:
            estado = str(pedido.wa_estado or "")
            ultimo = pedido.wa_ultimo_contacto
            if not ultimo:
                continue
            elapsed = (ahora - ultimo).total_seconds()

            if estado in ["esperando_confirmacion_sucursal", "esperando_datos", "falta_elegir_transporte"]:
                if elapsed >= TIMER_SEGUNDO_RECORDATORIO and not _ya_envio_recordatorio(pedido, 2):
                    wa_enviar_recordatorio_2(pedido)
                    _marcar_recordatorio(pedido, 2)
                elif elapsed >= TIMER_PRIMER_RECORDATORIO and not _ya_envio_recordatorio(pedido, 1):
                    wa_enviar_recordatorio_1(pedido)
                    _marcar_recordatorio(pedido, 1)
                elif elapsed >= TIMER_SEGUNDO_RECORDATORIO + 3600 and _ya_envio_recordatorio(pedido, 2):
                    _escalar_sin_respuesta(pedido)

            elif estado.startswith("cross_sell:") and estado != "cross_sell_cerrado":
                if elapsed >= TIMER_CROSS_SELL_SIGUIENTE:
                    partes = estado.split(":")
                    try:
                        indice = int(partes[-1]) if partes[-1].isdigit() else 0
                    except Exception:
                        indice = 0
                    from .cross_sell import obtener_productos_a_ofrecer, wa_ofrecer_producto, wa_cerrar_cross_sell
                    from app import normalizar_telefono
                    tel = normalizar_telefono(pedido.telefono)
                    productos = obtener_productos_a_ofrecer(pedido)
                    siguiente_idx = indice + 1
                    if siguiente_idx < len(productos):
                        siguiente_sku = productos[siguiente_idx]
                        _guardar_estado_wa(pedido, f"cross_sell:{siguiente_sku}:{siguiente_idx}")
                        wa_ofrecer_producto(tel, siguiente_sku)
                    else:
                        wa_cerrar_cross_sell(tel)
                        _guardar_estado_wa(pedido, "cross_sell_cerrado")
    except Exception as e:
        _cerrar_sesion_db_segura(rollback=True)
        print("[WA SCHEDULER] Error WA:", e)
    finally:
        _cerrar_sesion_db_segura(rollback=False)


def _es_transporte_tracking_auto_apb(pedido):
    """Tracking automático habilitado solo para Andreani y Via Cargo.

    Correo Argentino queda fuera de este scheduler para no mezclarlo con la
    integración WhatsApp/Correo que está en revisión. El tracking manual sigue
    disponible desde el detalle cuando corresponda.
    """
    transporte = str(getattr(pedido, "empresa_envio", "") or "").lower()
    return "andreani" in transporte or "via cargo" in transporte or "vía cargo" in transporte


def ejecutar_tracking_automatico():
    """Consulta tracking de Andreani/Via Cargo y trae el estado al resumen.

    Modo APB:
    - guarda estado externo, última sync, error y URL consultada;
    - autoavanza solo estados seguros;
    - NO marca Entregado automáticamente en Mercado Libre/Acordás la Entrega,
      porque antes debe intervenir el operador y avisar/confirmar en ML.
    """
    try:
        from app import (
            db, Pedido, tracking_info_pedido,
            aplicar_estado_tracking_seguro,
        )
        from services.tracking_externo import consultar_tracking_url, interpretar_estado_logistico
        from .post_despacho import registrar_tracking_evento, procesar_evento_tracking_pedido

        ahora = datetime.utcnow()
        limite = ahora - timedelta(minutes=TRACKING_INTERVALO_MINUTOS)

        pedidos = (
            Pedido.query
            .filter(Pedido.estado.in_([
                "Despachado",
                "Verificar llegada a destino",
                "Listo para retirar",
                "Con demora de entrega",
                "Con reclamo en transporte",
            ]))
            .filter(Pedido.seguimiento.isnot(None))
            .filter(Pedido.seguimiento != "")
            .filter((Pedido.tracking_ultima_sync.is_(None)) | (Pedido.tracking_ultima_sync < limite))
            .limit(25)
            .all()
        )

        for pedido in pedidos:
            if not _es_transporte_tracking_auto_apb(pedido):
                continue

            tracking_info = tracking_info_pedido(pedido)
            transporte = pedido.empresa_envio or ""
            seguimiento = (pedido.seguimiento or pedido.tn_tracking_number or "").strip()
            url = (tracking_info or {}).get("url") or ""

            try:
                if not url:
                    pedido.tracking_error = "No hay URL pública de seguimiento para consulta automática"
                    pedido.tracking_ultima_sync = ahora
                    db.session.commit()
                    continue

                resultado = consultar_tracking_url(url, transporte=transporte, seguimiento=seguimiento)

                estado = (resultado.get("estado") or "").strip() or "Sin estado detectado"
                clasificacion = interpretar_estado_logistico(estado, transporte=transporte)

                pedido.tracking_transportista = transporte[:80] if transporte else None
                pedido.tracking_url_consultada = url[:500] if url else None
                pedido.tracking_estado_externo = estado[:300]
                pedido.tracking_ultima_sync = ahora
                pedido.tracking_error = resultado.get("error")

                registrar_tracking_evento(
                    pedido, transporte, seguimiento, estado, clasificacion,
                    raw_json=str(resultado)[:4000], origen="scheduler"
                )

                nuevo_estado = None
                if not resultado.get("error"):
                    nuevo_estado = aplicar_estado_tracking_seguro(pedido, clasificacion)
                    procesar_evento_tracking_pedido(pedido, clasificacion, estado, origen="scheduler")

                db.session.commit()
                print(f"[TRACKING AUTO] Pedido #{pedido.id}: {transporte} {estado} → {clasificacion} / {nuevo_estado or pedido.estado}")
            except Exception as e:
                db.session.rollback()
                try:
                    pedido.tracking_error = str(e)
                    pedido.tracking_ultima_sync = ahora
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                print(f"[TRACKING AUTO] Error pedido #{pedido.id}:", e)
    except Exception as e:
        _cerrar_sesion_db_segura(rollback=True)
        print("[TRACKING AUTO] Error general:", e)
    finally:
        _cerrar_sesion_db_segura(rollback=False)


def _ya_envio_recordatorio(pedido, numero):
    return bool(getattr(pedido, f"wa_recordatorio_{numero}", None))


def _marcar_recordatorio(pedido, numero):
    try:
        from app import db
        setattr(pedido, f"wa_recordatorio_{numero}", True)
        pedido.wa_ultimo_contacto = datetime.utcnow()
        db.session.commit()
    except Exception as e:
        _cerrar_sesion_db_segura(rollback=True)
        print(f"[WA SCHEDULER] Error marcando recordatorio {numero}:", e)
    finally:
        _cerrar_sesion_db_segura(rollback=False)


def _escalar_sin_respuesta(pedido):
    try:
        from app import db
        if pedido.ia_requiere_operador:
            return
        pedido.ml_mensajes_pendientes = True
        pedido.ia_requiere_operador = True
        pedido.wa_estado = "sin_respuesta_escalado"
        resumen = (pedido.ia_resumen or "").strip()
        pedido.ia_resumen = f"{resumen} | WA: Cliente no respondió".strip(" |")
        db.session.commit()
    except Exception as e:
        _cerrar_sesion_db_segura(rollback=True)
        print("[WA SCHEDULER] Error escalando:", e)
    finally:
        _cerrar_sesion_db_segura(rollback=False)
