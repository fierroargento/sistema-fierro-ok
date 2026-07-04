import re

from .config import (
    WA_ESPERANDO_OK_INICIO,
    WA_ESPERANDO_DATOS,
    WA_ESPERANDO_CONFIRMACION_SUCURSAL,
    WA_LISTO_PARA_RETIRAR,
    WA_DESPACHO_EN_PROCESO,
    WA_DESPACHADO,
    WA_CONFIRMADO_CLIENTE,
    WA_POSTVENTA,
    WA_CROSS_SELL_CERRADO,
)

from .flows import (
    wa_procesar_respuesta_confirmacion,
    wa_procesar_datos_recibidos,
    wa_procesar_ok_inicio,
    wa_procesar_respuesta_cross_sell,
    wa_procesar_respuesta_postventa,
    wa_procesar_eleccion_transporte,
    _responder_factura_o_escalar,
    _escalar_operador,
    _wa_responder_con_ia,
    get_wa_paso_operativo,
)

from .sender import wa_enviar_texto
from .text_utils import es_agradecimiento_simple

from services.telefonos import normalizar_telefono_service
from services.wa_general_bot import manejar_sin_pedido_activo_wa_general


def routear_mensaje(
    pedido,
    texto,
    telefono,
    obtener_estado_wa,
):
    """
    Decide qué flujo manejar según el estado actual del pedido.
    """

    estado = obtener_estado_wa(pedido)
    paso_operativo = get_wa_paso_operativo(pedido)

    # Sin pedido activo
    if not pedido:
        from app import Pedido, WhatsAppMensaje

        manejar_sin_pedido_activo_wa_general(
            texto=texto,
            telefono=telefono,
            Pedido=Pedido,
            WhatsAppMensaje=WhatsAppMensaje,
            wa_enviar_texto=wa_enviar_texto,
        )
        return

    # Si un operador tomó la conversación, el bot NO responde automático.
    if estado == "operador_manual":

        try:
            from app import db

            pedido.ml_mensajes_pendientes = True
            pedido.ml_mensajes_pendientes_count = (
                pedido.ml_mensajes_pendientes_count or 0
            ) + 1

            pedido.ia_requiere_operador = True

            db.session.commit()

        except Exception as e:
            print(
                "[WA] No se pudo marcar pendiente operador:",
                e
            )

        return

    # Preguntas simples de factura
    if any(
        x in (texto or "").lower()
        for x in [
            "factura",
            "facturacion",
            "facturación",
            "factura a",
            "factura b",
        ]
    ):
        _responder_factura_o_escalar(
            pedido,
            texto,
        )
        return

    # Esperando confirmación de sucursal legacy
    if estado == WA_ESPERANDO_CONFIRMACION_SUCURSAL:

        wa_procesar_respuesta_confirmacion(
            pedido,
            texto,
        )

        return

    # Esperando elección transporte
    if estado == "falta_elegir_transporte":

        wa_procesar_eleccion_transporte(
            pedido,
            texto,
        )

        return

    # Esperando OK inicial
    if estado == WA_ESPERANDO_OK_INICIO:

        wa_procesar_ok_inicio(
            pedido,
            texto,
        )

        return

    # Esperando código postal
    if paso_operativo == "esperando_cp":

        cp_detectado = re.sub(
            r"\D",
            "",
            texto or "",
        )

        if len(cp_detectado) == 4:

            wa_procesar_datos_recibidos(
                pedido,
                cp_detectado,
            )

            return

        

        wa_enviar_texto(
            normalizar_telefono_service(telefono),
            "No llegué a detectar el código postal 😊\n\n¿Me lo pasás por acá?",
            pedido=pedido,
        )

        return

    # Esperando datos
    if estado == WA_ESPERANDO_DATOS:

        wa_procesar_datos_recibidos(
            pedido,
            texto,
        )

        return

    # Listo para retirar
    if estado == WA_LISTO_PARA_RETIRAR:

        from .text_utils import es_cierre_simple_retiro_post_aviso

        tel = normalizar_telefono_service(telefono)

        if es_cierre_simple_retiro_post_aviso(texto):
            wa_enviar_texto(
                tel,
                "¡Perfecto! Cualquier cosa que necesites, no dudes en avisar. ¡Que tengas un buen día!",
                pedido=pedido,
            )

            return

        _escalar_operador(
            pedido,
            "Cliente respondió luego de aviso de retiro",
            mensaje_cliente=texto,
        )

        return

    # Estados logísticos
    if estado in [
        WA_DESPACHO_EN_PROCESO,
        WA_DESPACHADO,
        WA_CONFIRMADO_CLIENTE,
    ]:

        texto_lower = (texto or "").lower()

        

        tel = normalizar_telefono_service(telefono)

        if es_agradecimiento_simple(texto):
            wa_enviar_texto(
                tel,
                "Gracias a vos! 😊",
                pedido=pedido,
            )

            return

        if any(
            x in texto_lower
            for x in [
                "retiro",
                "retirar",
                "retirarlo",
                "sucursal",
                "lo puedo retirar",
                "lo podre retirar",
                "lo podré retirar",
                "puedo pasar",
                "puedo ir",
            ]
        ):

            wa_enviar_texto(
                tel,
                "Todavía no te puedo confirmar que esté listo para retirar. En cuanto el transporte informe que está disponible en sucursal, te avisamos por acá 😊",
                pedido=pedido,
            )

            return

        if any(
            x in texto_lower
            for x in [
                "seguimiento",
                "tracking",
                "estado",
                "donde esta",
                "dónde está",
                "cuando llega",
                "cuándo llega",
                "llego",
                "llegó",
                "ya salio",
                "ya salió",
            ]
        ):

            wa_enviar_texto(
                tel,
                "Estamos siguiendo el envío. En cuanto tengamos una novedad del transporte, te avisamos por acá 😊",
                pedido=pedido,
            )

            return

        _escalar_operador(
            pedido,
            f"Consulta fuera de flujo logístico APB: {texto[:80]}",
            "Te derivamos con un operador para ayudarte mejor 😊"
        )

        return

    # Cross sell
    if (
        estado.startswith("cross_sell:")
        and estado != WA_CROSS_SELL_CERRADO
    ):

        partes = estado.split(":")

        sku_actual = (
            partes[1]
            if len(partes) > 1
            else ""
        )

        try:
            indice = (
                int(partes[-1])
                if partes[-1].isdigit()
                else 0
            )

        except Exception:
            indice = 0

        wa_procesar_respuesta_cross_sell(
            pedido,
            texto,
            sku_actual,
            indice,
        )

        return

    # Postventa
    if estado == WA_POSTVENTA:

        wa_procesar_respuesta_postventa(
            pedido,
            texto,
        )

        return

    # Fallback IA
    

    _wa_responder_con_ia(
        pedido,
        texto,
        normalizar_telefono_service(telefono),
    )
