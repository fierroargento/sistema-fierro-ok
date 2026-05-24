from datetime import datetime, UTC

from modules.whatsapp.config import (
    WA_DESPACHADO,
    WA_FINALIZADO,
    WA_TEMPLATE_PEDIDO_DATO,
    WA_TEMPLATE_POSTVENTA_PARRILLA,
    WA_TEMPLATE_RETIRO,
    WA_TEMPLATE_SEGUIMIENTO,
)
from modules.whatsapp.sender import wa_enviar_template, wa_enviar_texto
from services.telefonos import normalizar_telefono_service
from services.tracking_info import tracking_info_pedido_service


def wa_enviar_numero_seguimiento(pedido):
    from modules.whatsapp.flows import _guardar_estado_wa

    tel = normalizar_telefono_service(pedido.telefono)
    if not tel:
        return False

    seguimiento = (
        getattr(pedido, "seguimiento", "")
        or getattr(pedido, "tn_tracking_number", "")
        or ""
    ).strip()

    if not seguimiento:
        return False

    empresa = pedido.empresa_envio or "Correo Argentino"
    tracking_info = tracking_info_pedido_service(pedido) or {}
    link = tracking_info.get("url") or ""

    ok = wa_enviar_template(
        tel,
        WA_TEMPLATE_SEGUIMIENTO,
        parametros=[
            (getattr(pedido, "cliente", "") or "Cliente").split()[0],
            empresa,
            seguimiento,
            link,
        ],
        pedido=pedido,
        autor="bot",
    )

    if ok:
        _guardar_estado_wa(pedido, WA_DESPACHADO, tel)

    return ok


def wa_enviar_listo_para_retirar(pedido):
    from app import db

    tel = normalizar_telefono_service(pedido.telefono)
    if not tel:
        return False

    if getattr(pedido, "wa_listo_retirar_enviado", False):
        return False

    direccion_retiro = (
        getattr(pedido, "direccion", "")
        or getattr(pedido, "sucursal_nombre", "")
        or "Punto de retiro informado por el transporte"
    )

    seguimiento = (
        getattr(pedido, "seguimiento", "")
        or getattr(pedido, "tn_tracking_number", "")
        or ""
    ).strip()

    ok = wa_enviar_template(
        tel,
        WA_TEMPLATE_RETIRO,
        parametros=[
            (getattr(pedido, "cliente", "") or "Cliente").split()[0],
            direccion_retiro,
            seguimiento or "Sin número informado",
        ],
        pedido=pedido,
        autor="bot",
    )

    if ok:
        try:
            pedido.wa_listo_retirar_enviado = True
            pedido.wa_ultimo_contacto = datetime.now(UTC)
            db.session.commit()
        except Exception:
            db.session.rollback()

    return ok


def wa_enviar_postventa(pedido):
    from app import db

    tel = normalizar_telefono_service(pedido.telefono)
    if not tel:
        return False

    if getattr(pedido, "wa_postventa_enviada", False):
        return False

    ok = wa_enviar_template(
        tel,
        WA_TEMPLATE_POSTVENTA_PARRILLA,
        parametros=[
            (getattr(pedido, "cliente", "") or "Cliente").split()[0],
            "https://www.instagram.com/fierroargento",
        ],
        pedido=pedido,
        autor="bot",
    )

    if ok:
        try:
            pedido.wa_postventa_enviada = True
            pedido.wa_estado = WA_FINALIZADO
            pedido.wa_ultimo_contacto = datetime.now(UTC)
            db.session.commit()
        except Exception:
            db.session.rollback()

    return ok


def wa_procesar_respuesta_postventa(pedido, texto_cliente):
    from modules.whatsapp.flows import (
        _es_afirmativo,
        _es_queja_o_problema,
        _escalar_operador,
        _wa_responder_con_ia,
    )

    tel = normalizar_telefono_service(pedido.telefono)

    if _es_queja_o_problema(texto_cliente):
        _escalar_operador(
            pedido,
            "Problema postventa",
            "Te derivamos con un operador para ayudarte mejor.",
        )
        return

    if _es_afirmativo(texto_cliente) or "gracias" in texto_cliente.lower():
        wa_enviar_texto(tel, "Gracias a vos! Un placer.")
        return

    _wa_responder_con_ia(pedido, texto_cliente, tel)


def wa_enviar_recordatorio_1(pedido):
    tel = normalizar_telefono_service(pedido.telefono)
    if not tel:
        return False

    nombre = (
        getattr(pedido, "nombre", None)
        or getattr(pedido, "cliente", None)
        or "Cliente"
    ).split()[0]

    return wa_enviar_template(
        tel,
        WA_TEMPLATE_PEDIDO_DATO,
        parametros=[
            nombre,
            (
                "Te escribimos nuevamente porque todavía necesitamos tu respuesta "
                "para poder avanzar con el despacho de tu pedido.\n\n"
                "Cuando puedas, respondé este mensaje así continuamos."
            ),
        ],
        pedido=pedido,
        autor="bot",
    )


def wa_enviar_recordatorio_2(pedido):
    tel = normalizar_telefono_service(pedido.telefono)
    if not tel:
        return False

    nombre = (
        getattr(pedido, "nombre", None)
        or getattr(pedido, "cliente", None)
        or "Cliente"
    ).split()[0]

    return wa_enviar_template(
        tel,
        WA_TEMPLATE_PEDIDO_DATO,
        parametros=[
            nombre,
            (
                "Seguimos aguardando tu respuesta para poder continuar con el despacho "
                "de tu pedido.\n\n"
                "Si no recibimos respuesta, no podemos avanzar con el envío y eso "
                "genera un atraso en el proceso."
            ),
        ],
        pedido=pedido,
        autor="bot",
    )