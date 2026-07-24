from datetime import datetime, timedelta, UTC

from extensions import db
from models.pedido import Pedido
from models.whatsapp_mensaje import WhatsAppMensaje

from .app_bridge import (
    actualizar_estado_conversacional_wa,
    registrar_evento_operativo_wa,
)

from services.ia_mensajes import (
    ia_marcar_mensaje_bot_service,
    ia_marcar_respuesta_cliente_service,
    ia_puede_enviar_automatico_service,
)
from services.telefonos import normalizar_telefono_service
from services.busqueda_pedidos import (
    buscar_pedido_activo_por_telefono_service,
)



def _asegurar_fecha_utc(fecha):
    """
    Normaliza fechas para comparar ventana WhatsApp 24h.

    SQLAlchemy/PostgreSQL puede devolver datetimes naive aunque se hayan
    guardado desde datetime.now(UTC). Para la ventana 24h los interpretamos
    como UTC y evitamos mezclar aware vs naive.
    """
    if not fecha:
        return None

    if getattr(fecha, "tzinfo", None) is None:
        return fecha.replace(tzinfo=UTC)

    return fecha.astimezone(UTC)

def wa_ventana_24h_abierta_service(
    WhatsAppMensaje,
    pedido=None,
    telefono="",
):
    """
    Devuelve True si el cliente respondió
    por WhatsApp dentro de las últimas 24 hs.
    """

    try:
        tel_norm = normalizar_telefono_service(
            telefono or (
                getattr(pedido, "telefono", "")
                if pedido else ""
            )
        )

        query = WhatsAppMensaje.query.filter(
            WhatsAppMensaje.direccion == "in"
        )

        if pedido is not None:
            query = query.filter(
                WhatsAppMensaje.pedido_id == pedido.id
            )

        elif tel_norm:
            query = query.filter(
                WhatsAppMensaje.telefono == tel_norm
            )

        else:
            return False

        ultimo = query.order_by(
            WhatsAppMensaje.fecha.desc()
        ).first()

        if not ultimo or not ultimo.fecha:
            return False

        fecha_ultimo = _asegurar_fecha_utc(ultimo.fecha)
        if not fecha_ultimo:
            return False

        return (
            datetime.now(UTC) - fecha_ultimo
        ) <= timedelta(hours=24)

    except Exception as e:
        print("[WA] No se pudo evaluar ventana 24h:", e)
        return False


def wa_ventana_24h_abierta(
    pedido=None,
    telefono="",
):
    """Evalúa la ventana de 24 h usando el modelo canónico."""
    return wa_ventana_24h_abierta_service(
        WhatsAppMensaje,
        pedido=pedido,
        telefono=telefono,
    )


def registrar_whatsapp_mensaje_service(
    WhatsAppMensaje,
    actualizar_estado_conversacional,
    registrar_evento_operativo,
    Pedido,
    db,
    pedido=None,
    telefono="",
    direccion="",
    autor="",
    texto="",
    message_id_meta="",
    estado="",
    error="",
):
    """
    Guarda un mensaje WA
    sin romper el flujo si falla la auditoría.
    """

    try:
        tel_norm = normalizar_telefono_service(
            telefono or (
                getattr(pedido, "telefono", "")
                if pedido else ""
            )
        )

        if pedido is None and tel_norm:
            pedido = buscar_pedido_activo_por_telefono_service(
                tel_norm,
                Pedido,
            )

        ahora = datetime.now(UTC)

        msg = WhatsAppMensaje(
            pedido_id=getattr(pedido, "id", None),
            telefono=tel_norm or str(telefono or ""),
            direccion=(direccion or "")[:10],
            autor=(autor or "")[:30],
            texto=str(texto or ""),
            message_id_meta=str(message_id_meta or "")[:120],
            estado=(estado or "")[:40],
            error=str(error or "")[:1000] if error else "",
            fecha=ahora,
        )

        db.session.add(msg)

        if pedido is not None:
            pedido.wa_ultimo_contacto = ahora

        db.session.commit()

        if pedido is not None:

            actualizar_estado_conversacional(
                pedido,
                canal_activo="wa",
                ultimo_mensaje_cliente=(
                    ahora if direccion == "in"
                    else None
                ),
                ultimo_mensaje_bot=(
                    ahora if direccion == "out"
                    else None
                ),
            )

        registrar_evento_operativo(
            pedido=pedido,
            tipo_evento="whatsapp_mensaje_registrado",
            origen=autor or "sistema",
            canal="wa",
            owner=(
                "bot"
                if autor in ["bot", "sistema"]
                else "operador"
            ),
            payload={
                "direccion": direccion,
                "estado": estado,
                "message_id_meta": message_id_meta,
            },
            detalle=(texto or "")[:500],
            procesado=True,
        )

        return msg

    except Exception as e:

        try:
            db.session.rollback()
        except Exception:
            pass

        print("[WA-HIST] No se pudo registrar mensaje:", e)

        return None


def ia_marcar_mensaje_bot(
    pedido,
    canal,
    texto=None,
    commit=True,
):
    """Marca una salida del bot con dependencias canónicas."""
    return ia_marcar_mensaje_bot_service(
        pedido,
        canal,
        actualizar_estado_conversacional_wa,
        registrar_evento_operativo_wa,
        db.session,
        texto=texto,
        commit=commit,
    )


def ia_marcar_respuesta_cliente(
    pedido,
    canal=None,
    commit=True,
):
    """Libera la espera usando dependencias canónicas."""
    return ia_marcar_respuesta_cliente_service(
        pedido,
        actualizar_estado_conversacional_wa,
        registrar_evento_operativo_wa,
        db.session,
        canal=canal,
        commit=commit,
    )


def ia_puede_enviar_automatico(
    pedido,
    canal,
    texto=None,
    permitir_requiere_operador=False,
):
    """Evalúa el candado automático canónico."""
    return ia_puede_enviar_automatico_service(
        pedido,
        canal,
        texto=texto,
        permitir_requiere_operador=(
            permitir_requiere_operador
        ),
    )


def registrar_whatsapp_mensaje(
    pedido=None,
    telefono="",
    direccion="",
    autor="",
    texto="",
    message_id_meta="",
    estado="",
    error="",
):
    """Registra historial WA usando dependencias canónicas."""
    return registrar_whatsapp_mensaje_service(
        WhatsAppMensaje,
        actualizar_estado_conversacional_wa,
        registrar_evento_operativo_wa,
        Pedido,
        db,
        pedido=pedido,
        telefono=telefono,
        direccion=direccion,
        autor=autor,
        texto=texto,
        message_id_meta=message_id_meta,
        estado=estado,
        error=error,
    )
