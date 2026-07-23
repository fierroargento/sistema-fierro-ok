"""
modules/whatsapp/scheduler.py
──────────────────────────────
Scheduler central APB.

Se ejecuta periódicamente desde modules.whatsapp.activar(app), enganchado a before_request.
No abre threads ni procesos extra, para no complicar Render.
"""

from datetime import datetime, timedelta, UTC
from threading import Lock

from extensions import db
from models.pedido import Pedido

from domain.estados import Estado, ESTADOS_POST_DESPACHO
from services.logger import get_app_logger

logger = get_app_logger(__name__)

_scheduler_lock = Lock()


def _cerrar_sesion_db_segura(rollback=False):
    """Limpieza defensiva de SQLAlchemy para schedulers/background jobs.

    En Render/Postgres puede cortarse SSL; si queda una transacción inválida,
    SQLAlchemy exige rollback antes de reutilizar la conexión. Este helper evita
    que un error de scheduler rompa requests normales.
    """
    try:
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
    TRACKING_INTERVALO_MINUTOS,
    WA_ESPERANDO_DATOS,
    WA_ESPERANDO_CONFIRMACION_SUCURSAL,
    modulo_activo,
)


def ejecutar_timers():
    """Punto único de scheduler.

    Protegido contra ejecuciones simultáneas: el módulo puede dispararse desde
    APScheduler y también desde el hook liviano de requests. Si se solapan, se
    saltea una vuelta para no compartir sesión DB ni duplicar consultas externas.
    """
    if not _scheduler_lock.acquire(blocking=False):
        logger.info("[WA SCHEDULER] Tick omitido: ya hay un scheduler corriendo")
        return

    hubo_error = False
    try:
        ejecutar_timers_whatsapp()
        ejecutar_tracking_automatico()
    except Exception as e:
        hubo_error = True
        logger.exception("[WA SCHEDULER] Error general ejecutar_timers")
    finally:
        _cerrar_sesion_db_segura(rollback=hubo_error)
        _scheduler_lock.release()


def ejecutar_timers_whatsapp():
    """APB WhatsApp.

    Recordatorios por template:
    - +24 hs sin respuesta: recordatorio 1
    - +48 hs sin respuesta: recordatorio 2
    - +72 hs sin respuesta: escala operador

    Solo aplica a estados críticos donde esperamos respuesta del cliente:
    - esperando_datos
    - esperando_confirmacion_sucursal
    """
    if not modulo_activo():
        return

    try:
        from app import ia_ahora_utc, ia_escalar_si_timeout_operativo
        from modules.whatsapp.flows import (
            wa_enviar_recordatorio_1,
            wa_enviar_recordatorio_2,
        )
        from services.canal_manager import wa_puede_gobernar_timeout

        ahora = ia_ahora_utc()

        pedidos = (
            Pedido.query
            .filter(Pedido.ia_esperando_respuesta == True)
            .filter(Pedido.ia_ultimo_mensaje_bot.isnot(None))
            .filter(Pedido.estado.notin_([
                Estado.ENTREGADO,
                Estado.FINALIZADO,
                Estado.CANCELADO,
            ]))
            .filter(Pedido.wa_estado.in_([
                WA_ESPERANDO_DATOS,
                WA_ESPERANDO_CONFIRMACION_SUCURSAL,
            ]))
            .limit(100)
            .all()
        )

        for pedido in pedidos:
            if not wa_puede_gobernar_timeout(pedido):
                continue

            ultimo_bot = getattr(pedido, "ia_ultimo_mensaje_bot", None)
            if not ultimo_bot:
                continue

            segundos = int((ahora - ultimo_bot).total_seconds())

            if segundos >= 72 * 60 * 60:
                ia_escalar_si_timeout_operativo(
                    pedido,
                    canal="whatsapp",
                )
                continue

            if segundos >= 48 * 60 * 60 and not getattr(pedido, "wa_recordatorio_2", False):
                if wa_enviar_recordatorio_2(pedido):
                    pedido.wa_recordatorio_2 = True
                    db.session.commit()
                continue

            if segundos >= 24 * 60 * 60 and not getattr(pedido, "wa_recordatorio_1", False):
                if wa_enviar_recordatorio_1(pedido):
                    pedido.wa_recordatorio_1 = True
                    db.session.commit()
                continue

    except Exception as e:
        _cerrar_sesion_db_segura(rollback=True)
        logger.exception("[WA SCHEDULER] Error WA")
    finally:
        _cerrar_sesion_db_segura(rollback=False)
def _es_transporte_tracking_auto_apb(pedido):
    """Tracking automático habilitado para Correo Argentino y Mercado Envíos.

    Andreani y Vía Cargo quedan fuera hasta tener integración/API estable.
    Mercado Envíos se trata operativamente como Correo para consultar tracking,
    pero los blindajes de workflow evitan cerrar o avanzar pedidos por duplicado.
    """
    transporte = str(getattr(pedido, "empresa_envio", "") or "").lower().replace("í", "i")
    ml_tipo = str(getattr(pedido, "ml_tipo", "") or "").lower().replace("í", "i")

    return "correo" in transporte or "mercado envios" in transporte or "mercado envios" in ml_tipo

def ejecutar_tracking_automatico():
    """Consulta tracking de Correo/Mercado Envíos y trae el estado al resumen.

    Modo APB:
    - guarda estado externo, última sync, error y URL consultada;
    - autoavanza solo estados seguros;
    - NO marca Entregado automáticamente en Mercado Libre/Acordás la Entrega,
      porque antes debe intervenir el operador y avisar/confirmar en ML.
    """
    try:
        from app import (
            tracking_info_pedido,
            aplicar_estado_tracking_seguro,
        )
        from services.tracking_externo import consultar_tracking_url, interpretar_estado_logistico, consultar_correo_formulario
        from .post_despacho import registrar_tracking_evento, procesar_evento_tracking_pedido

        ahora = datetime.now(UTC)
        limite = ahora - timedelta(minutes=TRACKING_INTERVALO_MINUTOS)

        pedidos = (
            Pedido.query
            .filter(Pedido.estado.in_(ESTADOS_POST_DESPACHO))
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
                transporte_norm = (transporte or "").strip().lower().replace("í", "i")
                ml_tipo_norm = str(getattr(pedido, "ml_tipo", "") or "").strip().lower().replace("í", "i")
                canal_norm = str(getattr(pedido, "canal", "") or "").strip()

                es_mercado_envios = (
                    "mercado envios" in ml_tipo_norm
                    or "mercado envios" in transporte_norm
                )
                es_correo_tracking = "correo" in transporte_norm or es_mercado_envios
                url_para_registro = url

                if "andreani" in transporte_norm:
                    pedido.tracking_error = "Tracking automático Andreani desactivado hasta integración API"
                    pedido.tracking_ultima_sync = ahora
                    db.session.commit()
                    continue

                if "via cargo" in transporte_norm:
                    pedido.tracking_error = "Tracking automático Vía Cargo desactivado hasta integración API"
                    pedido.tracking_ultima_sync = ahora
                    db.session.commit()
                    continue

                if es_correo_tracking:
                    resultado = consultar_correo_formulario(
                        seguimiento,
                        mercado_envios=(
                            canal_norm == "Mercado Libre"
                            and es_mercado_envios
                        ),
                    )
                    transporte = "Correo Argentino"
                    url_para_registro = url or "micorreo"
                else:
                    if not url:
                        pedido.tracking_error = "No hay URL pública de seguimiento para consulta automática"
                        pedido.tracking_ultima_sync = ahora
                        db.session.commit()
                        continue

                    resultado = consultar_tracking_url(
                        url,
                        transporte=transporte,
                        seguimiento=seguimiento
                    )

                estado = (resultado.get("estado") or "").strip() or "Sin estado detectado"
                clasificacion = interpretar_estado_logistico(estado, transporte=transporte)

                pedido.tracking_transportista = transporte[:80] if transporte else None
                pedido.tracking_url_consultada = url_para_registro[:500] if url_para_registro else None
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
                # APB LOGS:
                # Si el tracking automático no detecta estado útil,
                # no llenamos Render de ruido. El dato queda guardado en DB.
                if not (
                    estado == "Sin estado detectado"
                    and clasificacion == "desconocido"
                    and not nuevo_estado
                ):
                    print(
                        f"[TRACKING AUTO] Pedido #{pedido.id}: "
                        f"{transporte} {estado} → {clasificacion} / "
                        f"{nuevo_estado or pedido.estado}"
                    )
            except Exception as e:
                db.session.rollback()
                try:
                    pedido.tracking_error = str(e)
                    pedido.tracking_ultima_sync = ahora
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                logger.exception(
    "[TRACKING AUTO] Error pedido #%s",
    getattr(pedido, "id", ""),
)
    except Exception as e:
        _cerrar_sesion_db_segura(rollback=True)
        logger.exception("[TRACKING AUTO] Error general")
    finally:
        _cerrar_sesion_db_segura(rollback=False)
