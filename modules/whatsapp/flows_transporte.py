import json
import re
from datetime import datetime, UTC

from services.telefonos import normalizar_telefono_service

from modules.whatsapp.app_bridge import (
    actualizar_estado_conversacional_wa,
    registrar_evento_operativo_wa,
)



from modules.whatsapp.config import (
    WA_DESPACHO_EN_PROCESO,
    WA_ESPERANDO_CONFIRMACION_SUCURSAL,
    WA_FALTA_ELEGIR_TRANSPORTE,
    WA_TEMPLATE_INICIO_CHAT_OPERADOR,
)

from modules.whatsapp.sender import wa_enviar_texto

from modules.whatsapp.config import (
    WA_DESPACHO_EN_PROCESO,
    WA_FALTA_ELEGIR_TRANSPORTE,
    WA_TEMPLATE_INICIO_CHAT_OPERADOR,
)
def _cargar_sucursales_ofrecidas(pedido):
    raw = getattr(pedido, "correo_sucursales_ofrecidas", None) or getattr(pedido, "ia_sucursales_ofrecidas", "") or ""
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []
    
def wa_enviar_confirmacion_sucursal(pedido):
    
    tel = normalizar_telefono_service(pedido.telefono)
    if not tel:
        return False
    nombre_base = (getattr(pedido, "nombre", None) or getattr(pedido, "cliente", None) or "")
    nombre = nombre_base.split()[0] if nombre_base else "Cliente"
    texto = (
        f"Hola {nombre}!\n\n"
        f"Tu pedido se despacha a:\n"
        f"{pedido.sucursal_nombre or 'Sucursal elegida'}\n"
        f"{pedido.direccion or ''}\n\n"
        f"Confirmás que está correcto?"
    )
    _guardar_estado_wa(
    pedido,
    WA_ESPERANDO_CONFIRMACION_SUCURSAL,
    tel
)
    return wa_enviar_texto(tel, texto)

def wa_procesar_respuesta_confirmacion(pedido, texto_cliente):
    from modules.whatsapp.flows import (
        _es_afirmativo,
        _es_negativo,
        _es_consulta_factura,
        _responder_factura_o_escalar,
        _wa_responder_con_ia,
        _guardar_estado_wa,
        _escalar_operador,
        wa_iniciar_cross_sell,
    )

    tel = normalizar_telefono_service(pedido.telefono)

    if _es_consulta_factura(texto_cliente):
        return _responder_factura_o_escalar(pedido, texto_cliente)

    if _es_afirmativo(texto_cliente):
        _guardar_estado_wa(pedido, WA_DESPACHO_EN_PROCESO, tel)
        wa_enviar_texto(
            tel,
            "Perfecto, ya tenemos todo para avanzar con el despacho.\n\nEn breve te pasamos los detalles del envío y el seguimiento.",
            pedido=pedido,
            fallback_template=WA_TEMPLATE_INICIO_CHAT_OPERADOR,
            fallback_parametros=[
                (getattr(pedido, "cliente", "") or "Cliente").split()[0],
                pedido.id_venta or pedido.id or "",
            ],
        )
        wa_iniciar_cross_sell(pedido)
        return

    if _es_negativo(texto_cliente):
        _escalar_operador(pedido, "Cliente no confirmó sucursal")
        return

    _wa_responder_con_ia(pedido, texto_cliente, tel)

def wa_procesar_eleccion_transporte(pedido, texto_cliente):
    from app import db
    from modules.transportes.selector import asignar_transporte_pedido
    from modules.whatsapp.flows import (
        _es_afirmativo,
        _es_consulta_factura,
        _es_queja_o_problema,
        _escalar_operador,
        _responder_factura_o_escalar,
        _guardar_estado_wa,
    )

    tel = normalizar_telefono_service(pedido.telefono)
    texto = (texto_cliente or "").strip().lower()

    if _es_consulta_factura(texto_cliente):
        return _responder_factura_o_escalar(pedido, texto_cliente)

    if any(x in texto for x in ["domicilio", "a casa", "mi casa", "entrega en casa"]):
        ok, msg = asignar_transporte_pedido(
            pedido,
            preferencia_cliente="domicilio"
        )

        if ok:
            _guardar_estado_wa(
                pedido,
                WA_DESPACHO_EN_PROCESO,
                tel
            )

            wa_enviar_texto(
                tel,
                "Perfecto, ya tenemos todo para avanzar con el despacho.\n\nEn breve te pasamos los detalles del envío y el seguimiento.",
                pedido=pedido,
                fallback_template=WA_TEMPLATE_INICIO_CHAT_OPERADOR,
                fallback_parametros=[
                    (getattr(pedido, "cliente", "") or "Cliente").split()[0],
                    pedido.id_venta or pedido.id or "",
                ],
            )

            return

        _escalar_operador(
            pedido,
            msg or "Cliente pidió domicilio y requiere revisión",
            "Siempre recomendamos retiro en sucursal o punto Correo porque suele ser más ordenado y evita posibles demoras por visitas fallidas en domicilio.\n\nDe todas maneras, lo revisamos con un operador y te confirmamos."
        )

        return

    if _es_queja_o_problema(texto_cliente):
        _escalar_operador(
            pedido,
            "Consulta/problema en elección de transporte",
            "Te derivamos con un operador para ayudarte mejor."
        )

        return

    sucs = _cargar_sucursales_ofrecidas(pedido)

    from services.mensajes_sucursales import (
        normalizar_numero_opcion_sucursal,
        texto_pide_opcion_numerica_sucursal,
    )

    idx_normalizado = normalizar_numero_opcion_sucursal(texto)

    if idx_normalizado is not None and sucs:
        idx = idx_normalizado

        if 0 <= idx < len(sucs):
            suc = sucs[idx]

            if not (pedido.empresa_envio or "").strip():
                pedido.empresa_envio = "Vía Cargo"

            pedido.tipo_entrega = "Sucursal"

            pedido.sucursal_nombre = (
                suc.get("nombre")
                or suc.get("name")
                or pedido.sucursal_nombre
            )

            pedido.direccion = (
                suc.get("direccion")
                or suc.get("address")
                or pedido.direccion
            )

            pedido.localidad = (
                suc.get("localidad")
                or suc.get("city")
                or pedido.localidad
            )

            pedido.provincia = (
                suc.get("provincia")
                or pedido.provincia
            )

            pedido.wa_estado = WA_DESPACHO_EN_PROCESO
            pedido.wa_ultimo_contacto = datetime.now(UTC)

            db.session.commit()

            wa_enviar_texto(
                tel,
                "Perfecto, ya tenemos todo para avanzar con el despacho.\n\nEn breve te pasamos los detalles del envío y el seguimiento.",
                pedido=pedido,
                fallback_template=WA_TEMPLATE_INICIO_CHAT_OPERADOR,
                fallback_parametros=[
                    (getattr(pedido, "cliente", "") or "Cliente").split()[0],
                    pedido.id_venta or pedido.id or "",
                ],
            )

            return

    if _es_afirmativo(texto) and sucs:
        if len(sucs) == 1:
            suc = sucs[0]

            if not (pedido.empresa_envio or "").strip():
                pedido.empresa_envio = "Vía Cargo"

            pedido.tipo_entrega = "Sucursal"

            pedido.sucursal_nombre = (
                suc.get("nombre")
                or suc.get("name")
                or pedido.sucursal_nombre
            )

            pedido.direccion = (
                suc.get("direccion")
                or suc.get("address")
                or pedido.direccion
            )

            pedido.localidad = (
                suc.get("localidad")
                or suc.get("city")
                or pedido.localidad
            )

            pedido.provincia = (
                suc.get("provincia")
                or suc.get("state")
                or pedido.provincia
            )

            try:
                _guardar_estado_wa(
                    pedido,
                    WA_DESPACHO_EN_PROCESO,
                    tel
                )

                db.session.commit()
            except Exception:
                db.session.rollback()

            wa_enviar_texto(
                tel,
                "Perfecto, ya tenemos todo para avanzar con el despacho.\n\n"
                "En breve te pasamos los detalles del envío y el seguimiento.",
                pedido=pedido,
                fallback_template=WA_TEMPLATE_INICIO_CHAT_OPERADOR,
                fallback_parametros=[
                    (getattr(pedido, "cliente", "") or "Cliente").split()[0],
                    pedido.id_venta or pedido.id or "",
                ],
            )

            try:
                from modules.whatsapp.flows import wa_iniciar_cross_sell

                wa_iniciar_cross_sell(pedido)
            except Exception as e:
                print("[WA] Error iniciando cross sell luego de confirmar sucursal única:", e)

            return

        wa_enviar_texto(
            tel,
            texto_pide_opcion_numerica_sucursal()
        )
        return

    _escalar_operador(
        pedido,
        f"Respuesta no clara sobre transporte: {texto_cliente[:120]}",
        "Lo revisamos con un operador para no cometer errores en el despacho."
    )

def wa_cerrar_datos_completos(pedido):
    """Datos completos: para PP6040 prepara Correo y no informa costos al cliente."""

    from app import db
    from modules.transportes.selector import (
        pedido_contiene_pp6040,
        asignar_transporte_pedido,
        sugerir_sucursales_correo_pedido,
    )
    from modules.whatsapp.flows import (
        _guardar_estado_wa,
        _escalar_operador,
    )

    tel = normalizar_telefono_service(pedido.telefono)

    if not tel:
        return False

    actualizar_estado_conversacional_wa(
        pedido,
        owner_actual="bot",
        canal_activo="wa",
        estado_conversacional="datos_completos",
        takeover_activo=False,
        bot_pausado=False,
    )

    registrar_evento_operativo_wa(
        pedido=pedido,
        tipo_evento="datos_completos",
        origen="bot",
        canal="wa",
        owner="bot",
        estado_conversacional="datos_completos",
        payload={
            "wa_estado": getattr(pedido, "wa_estado", ""),
            "estado_pedido": getattr(pedido, "estado", ""),
            "telefono": tel,
        },
        resultado="ok",
        detalle="WhatsApp cerró la recolección con datos completos.",
        procesado=True,
    )

    if pedido_contiene_pp6040(pedido):
        ok, msg = asignar_transporte_pedido(
            pedido,
            preferencia_cliente="sucursal"
        )

        msg_suc = sugerir_sucursales_correo_pedido(pedido)

        if msg_suc:
            _guardar_estado_wa(
                pedido,
                WA_FALTA_ELEGIR_TRANSPORTE,
                tel
            )

            return wa_enviar_texto(
                tel,
                msg_suc
            )

        if ok:
            _guardar_estado_wa(
                pedido,
                WA_DESPACHO_EN_PROCESO,
                tel
            )

            return wa_enviar_texto(
                tel,
                "Perfecto, ya tenemos todos los datos para avanzar con el despacho.\n\nEn breve te pasamos los detalles del envío y el seguimiento.",
                pedido=pedido,
                fallback_template=WA_TEMPLATE_INICIO_CHAT_OPERADOR,
                fallback_parametros=[
                    (getattr(pedido, "cliente", "") or "Cliente").split()[0],
                    pedido.id_venta or pedido.id or "",
                ],
            )

        _escalar_operador(
            pedido,
            msg or "No se pudo resolver transporte Correo"
        )

        return False

    try:
        from app import aplicar_default_tipo_entrega

        if aplicar_default_tipo_entrega(pedido):
            db.session.commit()

    except Exception as e:
        print("[WA] No se pudo aplicar tipo_entrega por defecto:", e)

    _guardar_estado_wa(
        pedido,
        WA_DESPACHO_EN_PROCESO,
        tel
    )

    return wa_enviar_texto(
        tel,
        "Perfecto, ya tenemos todos los datos para avanzar con el despacho.\n\nEn breve te pasamos los detalles del envío y el seguimiento.",
        pedido=pedido,
        fallback_template=WA_TEMPLATE_INICIO_CHAT_OPERADOR,
        fallback_parametros=[
            (getattr(pedido, "cliente", "") or "Cliente").split()[0],
            pedido.id_venta or pedido.id or "",
        ],
    )        