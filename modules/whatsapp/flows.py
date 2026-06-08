"""
modules/whatsapp/flows.py
─────────────────────────
Flujos conversacionales WhatsApp — APB.

Alcance de esta etapa:
- WhatsApp es continuación operativa luego de Mercado Libre.
- PP6040 va por Correo Argentino.
- Cliente no ve costos: siempre envío sin cargo.
- Bot prioriza sucursal / punto Correo.
- Preguntas fiscales se responden con regla fija y se escalan si piden otros datos.
"""

import json
import re
from datetime import datetime, UTC
from domain.estados import Estado

from .config import (
    CROSS_SELL_MANUAL_ENABLED,
    CROSS_SELL_AUTO_ENABLED,
    WA_ESPERANDO_DATOS,
    WA_LISTO_PARA_RETIRAR,
    WA_ESPERANDO_OK_INICIO,    
    WA_FALTA_ELEGIR_TRANSPORTE,
    WA_REQUIERE_OPERADOR,
    WA_CONFIRMADO_CLIENTE,
    WA_DESPACHO_EN_PROCESO,
    WA_DESPACHADO,
    WA_POSTVENTA,
    WA_FINALIZADO,
    WA_CROSS_SELL_CERRADO,
    WA_TEMPLATE_PEDIDO_DATO,
    WA_TEMPLATE_INICIO_DESPACHO,
    WA_TEMPLATE_INICIO_CHAT_OPERADOR,
    WA_TEMPLATE_SEGUIMIENTO,
    WA_TEMPLATE_RETIRO,
    WA_TEMPLATE_POSTVENTA_PARRILLA,
    WA_ESPERANDO_CONFIRMACION_SUCURSAL,    
)

from modules.whatsapp.app_bridge import (
    actualizar_estado_conversacional_wa,
    registrar_evento_operativo_wa,
)

from modules.whatsapp.flows_postventa import (
    wa_enviar_numero_seguimiento,
    wa_enviar_listo_para_retirar,
    wa_enviar_postventa,
    wa_procesar_respuesta_postventa,
    wa_enviar_recordatorio_1,
    wa_enviar_recordatorio_2,
)

from .sender import wa_enviar_texto, wa_enviar_template
from .cross_sell import (
    obtener_productos_a_ofrecer, wa_ofrecer_producto,
    wa_responder_precio, wa_cerrar_cross_sell, wa_escalar_venta_cerrada,
)

from modules.whatsapp.text_utils import (
    es_afirmativo,
    es_negativo,
    pregunta_precio,
    pregunta_cantidad,
    es_queja_o_problema,
    es_consulta_factura,
    requiere_factura_distinta,
)

from modules.whatsapp.flows_transporte import (
    _cargar_sucursales_ofrecidas,
    wa_enviar_confirmacion_sucursal,
    wa_procesar_respuesta_confirmacion,
    wa_procesar_eleccion_transporte,
    wa_cerrar_datos_completos,
)

from services.telefonos import normalizar_telefono_service


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def get_wa_paso_operativo(pedido):
    return str(
        getattr(pedido, "wa_paso_operativo", "") or ""
    ).strip().lower()


def set_wa_paso_operativo(
    pedido,
    paso,
    commit=True,
):
    from app import db

    pedido.wa_paso_operativo = (
        str(paso or "").strip().lower()
    )

    if commit:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()


def limpiar_wa_paso_operativo(
    pedido,
    commit=True,
):
    from app import db

    pedido.wa_paso_operativo = None

    if commit:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

def _guardar_estado_wa(pedido, estado, tel=None):
    try:
        from app import db
        pedido.wa_estado = estado
        pedido.wa_ultimo_contacto = datetime.now(UTC)
        db.session.commit()
    except Exception as e:
        print("[WA] Error guardando estado:", e)


def _obtener_estado_wa(pedido):
    return str(getattr(pedido, "wa_estado", "") or "")


def _escalar_operador(pedido, motivo, mensaje_cliente=None):
    """Marca el pedido para atención humana sin romper ML."""
    try:
        from app import db
        pedido.ml_mensajes_pendientes = True
        pedido.ml_mensajes_pendientes_count = (pedido.ml_mensajes_pendientes_count or 0) + 1
        pedido.ia_requiere_operador = True
        pedido.wa_estado = WA_REQUIERE_OPERADOR
        resumen_actual = (pedido.ia_resumen or "").strip()
        pedido.ia_resumen = f"{resumen_actual} | WA: {motivo}".strip(" |")
        pedido.wa_ultimo_contacto = datetime.now(UTC)
        db.session.commit()
        print(f"[WA] Pedido #{pedido.id} escalado: {motivo}")

        if mensaje_cliente:
            tel = normalizar_telefono_service(pedido.telefono)
            if tel:
                wa_enviar_texto(tel, mensaje_cliente)
    except Exception as e:
        print("[WA] Error escalando:", e)


def _es_afirmativo(texto):
    return es_afirmativo(texto)


def _es_negativo(texto):
    return es_negativo(texto)


def _pregunta_precio(texto):
    return pregunta_precio(texto)


def _pregunta_cantidad(texto):
    return pregunta_cantidad(texto)


def _es_queja_o_problema(texto):
    return es_queja_o_problema(texto)


def _es_consulta_factura(texto):
    return es_consulta_factura(texto)


def _requiere_factura_distinta(texto):
    return requiere_factura_distinta(texto)


def _responder_factura_o_escalar(pedido, texto_cliente):
    
    tel = normalizar_telefono_service(pedido.telefono)
    if _requiere_factura_distinta(texto_cliente):
        _escalar_operador(
            pedido,
            "Cliente necesita factura con datos distintos a la plataforma",
            "Sí, realizamos factura A y B. Si necesitás que se emita con datos distintos a los cargados en la plataforma, te derivamos con un operador para revisarlo."
        )
        return True
    wa_enviar_texto(
        tel,
        "Sí, realizamos factura A y B.\n\nLa factura se emite con los datos cargados en la plataforma donde realizaste la compra."
    )
    return True


def _skus_str(pedido):
    items = pedido.items or []
    if not items:
        return "pedido"
    descripciones = [str(getattr(i, "descripcion", "") or getattr(i, "sku", "") or "producto") for i in items[:2]]
    return " y ".join(descripciones)


def _completar_localidad_provincia_por_cp(pedido):
    """Si hay CP y faltan localidad/provincia, intenta deducirlas sin pedir datos de más."""
    cp = str(getattr(pedido, "codigo_postal", "") or "").strip()
    if not cp or not cp.isdigit():
        return []
    if getattr(pedido, "localidad", None) and getattr(pedido, "provincia", None):
        return []

    completados = []
    try:
        # Primero usar CP de sucursales Via Cargo como base local validada del sistema.
        with open("via_cargo_sucursales.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        candidatas = [s for s in data if str(s.get("cp") or "").strip() == cp]
        if not candidatas and len(cp) >= 4:
            cp_int = int(cp)
            candidatas = sorted(
                [s for s in data if str(s.get("cp") or "").isdigit()],
                key=lambda s: abs(int(str(s.get("cp"))) - cp_int)
            )[:1]
        if candidatas:
            ref = candidatas[0]
            if not getattr(pedido, "localidad", None) and ref.get("localidad"):
                pedido.localidad = ref.get("localidad")
                completados.append("localidad")
            if not getattr(pedido, "provincia", None) and ref.get("provincia"):
                pedido.provincia = ref.get("provincia")
                completados.append("provincia")
            if completados:
                from app import db
                db.session.commit()
    except Exception as e:
        print("[WA] No se pudo autocompletar localidad/provincia por CP:", e)
    return completados


# ─────────────────────────────────────────────
# FLUJO DATOS
# ─────────────────────────────────────────────

def wa_iniciar_desde_ml(pedido):
    """
    Primer contacto formal WhatsApp luego de handoff desde ML.

    IMPORTANTE:
    - No pide datos todavía.
    - Solo busca abrir ventana 24 hs.
    - El cliente debe responder OK.
    """

    

    tel = normalizar_telefono_service(pedido.telefono)

    if not tel:
        return False

    nombre_base = (
        getattr(pedido, "nombre", None)
        or getattr(pedido, "cliente", None)
        or ""
    )

    nombre = nombre_base.split()[0] if nombre_base else ""

    ok = wa_enviar_template(
        tel,
        WA_TEMPLATE_INICIO_DESPACHO,
        parametros=[
            nombre or "Cliente",
            f"#{getattr(pedido, 'id_venta', '') or getattr(pedido, 'id', '')}",
        ],
        pedido=pedido,
        autor="bot",
    )

    if ok:
        _guardar_estado_wa(
            pedido,
            WA_ESPERANDO_OK_INICIO,
            tel,
        )

    return ok

def wa_enviar_solicitud_datos(pedido, faltantes):
    

    tel = normalizar_telefono_service(pedido.telefono)
    if not tel:
        return False

    nombre_base = (
        getattr(pedido, "nombre", None)
        or getattr(pedido, "cliente", None)
        or ""
    )
    nombre = nombre_base.split()[0] if nombre_base else "Cliente"

    campos_amigables = {
        "nombre": "nombre y apellido",
        "apellido": "apellido",
        "dni": "DNI",
        "direccion": "dirección completa",
        "localidad": "localidad",
        "provincia": "provincia",
        "codigo_postal": "código postal",
        "telefono": "teléfono",
    }

    faltantes_str = "\n".join(
        f"• {campos_amigables.get(f, f)}"
        for f in faltantes
    )

    _guardar_estado_wa(pedido, WA_ESPERANDO_DATOS, tel)

    # APB:
    # Guardamos el primer faltante operativo explícito.
    # El router WA debe responder según este paso,
    # no según IA libre.
    try:
        primer_faltante = (
            faltantes[0]
            if faltantes
            else ""
        )

        mapa_operativo = {
            "codigo_postal": "esperando_cp",
            "direccion": "esperando_direccion",
            "dni": "esperando_dni",
            "localidad": "esperando_localidad",
            "provincia": "esperando_provincia",
        }

        set_wa_paso_operativo(
            pedido,
            mapa_operativo.get(
                primer_faltante,
                WA_ESPERANDO_DATOS
            ),
            commit=False,
        )

    except Exception as e:
        print(
            "[WA-APB] No se pudo guardar paso operativo:",
            e,
        )

    return wa_enviar_template(
        tel,
        WA_TEMPLATE_PEDIDO_DATO,
        parametros=[
            nombre,
            faltantes_str,
        ],
        pedido=pedido,
        autor="bot",
    )

def wa_procesar_ok_inicio(pedido, texto_cliente):
    """
    Cliente respondió al template inicial WA.
    Ahora sí WhatsApp queda habilitado para continuar el flujo.
    """
    from app import  ia_faltantes_pedido

    tel = normalizar_telefono_service(pedido.telefono)
    if not tel:
        return False

    faltantes = ia_faltantes_pedido(pedido)

    if faltantes:
        return wa_enviar_solicitud_datos(pedido, faltantes)

    return wa_cerrar_datos_completos(pedido)

def wa_procesar_datos_recibidos(pedido, texto_cliente):
    from app import (
         ia_analizar_datos_cliente_ml_acordas,
        ia_guardar_resultado_recolector, ia_faltantes_pedido,
        ia_datos_previos_pedido, db,
    )
    tel = normalizar_telefono_service(pedido.telefono)

    if _es_consulta_factura(texto_cliente):
        return _responder_factura_o_escalar(pedido, texto_cliente)

    if _es_queja_o_problema(texto_cliente):
        _escalar_operador(pedido, "Queja durante recolección de datos", "Te derivamos con un operador para ayudarte mejor.")
        return

    resultado = ia_analizar_datos_cliente_ml_acordas(texto_cliente, ia_datos_previos_pedido(pedido))
    ia_guardar_resultado_recolector(pedido, texto_cliente, resultado)
    _completar_localidad_provincia_por_cp(pedido)

    faltantes = ia_faltantes_pedido(pedido)
    # No pedir localidad/provincia si se pudieron deducir por CP.
    faltantes = [f for f in faltantes if f not in ["localidad", "provincia"] or not getattr(pedido, f, None)]

    if not faltantes:

        tipo_ml = str(getattr(pedido, "tipo_ml", "") or "").lower()
        canal = str(getattr(pedido, "canal", "") or "").lower()

        es_ml_acordas = (
            canal == "mercado libre"
            and "acord" in tipo_ml
        )

        # APB:
        # ML Acordás SIEMPRE continúa por WhatsApp.
        if es_ml_acordas:

            wa_cerrar_datos_completos(pedido)

            try:
                wa_iniciar_cross_sell(pedido)
            except Exception as e:
                print("[WA] Error iniciando cross sell:", e)

            return

        wa_cerrar_datos_completos(pedido)
        return

    campos = {
        "nombre": "nombre y apellido",
        "apellido": "apellido",
        "dni": "DNI",
        "direccion": "dirección completa",
        "localidad": "localidad",
        "provincia": "provincia",
        "codigo_postal": "código postal",
    }
    wa_enviar_texto(
        tel,
        "Perfecto, gracias.\n\nTodavía me faltaría confirmar:\n\n" +
        "\n".join(f"• {campos.get(f, f)}" for f in faltantes) +
        "\n\nMe lo pasás por acá?",
        pedido=pedido,
        fallback_template=WA_TEMPLATE_PEDIDO_DATO,
        fallback_parametros=[
            (getattr(pedido, "cliente", "") or "Cliente").split()[0],
            ", ".join(campos.get(f, f) for f in faltantes[:3]),
        ],
    )
    pedido.wa_ultimo_contacto = datetime.now(UTC)
    db.session.commit()


# ─────────────────────────────────────────────
# CROSS-SELL
# ─────────────────────────────────────────────

def wa_iniciar_cross_sell(pedido, origen="bot", forzar=False):
    """
    Inicia el flujo de cross-sell por WhatsApp.

    Seguridad APB:
    - El automático queda apagado salvo CROSS_SELL_AUTO_ENABLED=true.
    - El manual queda apagado salvo CROSS_SELL_MANUAL_ENABLED=true.
    - El operador puede forzar el inicio aunque la conversación esté en modo manual.
    """

    origen = (origen or "bot").strip().lower()

    from services.cross_sell_rules import puede_iniciar_cross_sell_pedido

    modo_cross_sell = "operador" if origen == "operador" else "auto"

    if not puede_iniciar_cross_sell_pedido(
        pedido,
        modo=modo_cross_sell,
        auto_enabled=CROSS_SELL_AUTO_ENABLED,
        manual_enabled=CROSS_SELL_MANUAL_ENABLED,
        forzar=forzar,
    ):
        return False

    tel = normalizar_telefono_service(pedido.telefono)
    productos = obtener_productos_a_ofrecer(pedido)

    if not productos or not tel:
        return False

    empresa = str(getattr(pedido, "empresa_envio", "") or "").strip()
    tipo_entrega = str(getattr(pedido, "tipo_entrega", "") or "").strip()
    sucursal = str(getattr(pedido, "sucursal_nombre", "") or "").strip()

    primer_sku = productos[0]

    actualizar_estado_conversacional_wa(
        pedido,
        owner_actual="bot",
        canal_activo="wa",
        estado_conversacional="cross_sell",
        takeover_activo=False,
        bot_pausado=False,
        cross_sell_activo=True,
    )

    pedido.ia_requiere_operador = False

    texto_operativo = (
        "Perfecto, ya tenemos todo para avanzar con el despacho.\n\n"
    )

    if empresa:
        texto_operativo += f"El envío va a salir por *{empresa}*"
        if tipo_entrega:
            texto_operativo += f" con entrega en *{tipo_entrega}*"
        texto_operativo += ".\n"

    if sucursal:
        texto_operativo += f"\nSucursal seleccionada: *{sucursal}*.\n"

    texto_operativo += (
        "\nEn cuanto tengamos el número de seguimiento, te lo compartimos por acá."
    )

    ok_1 = wa_enviar_texto(
        tel,
        texto_operativo,
        pedido=pedido,
        autor=origen,
    )

    ok_2 = wa_enviar_texto(
        tel,
        "Aprovecho también para mostrarte algunos accesorios que suelen agregar junto con este pedido.",
        pedido=pedido,
        autor=origen,
    )

    _guardar_estado_wa(pedido, f"cross_sell:{primer_sku}:0", tel)

    ok_3 = wa_ofrecer_producto(tel, primer_sku)

    registrar_evento_operativo_wa(
        pedido=pedido,
        tipo_evento="cross_sell_iniciado",
        origen=origen,
        canal="wa",
        owner="bot",
        estado_conversacional="cross_sell",
        payload={
            "primer_sku": primer_sku,
            "productos": productos,
            "empresa_envio": empresa,
            "tipo_entrega": tipo_entrega,
            "sucursal": sucursal,
            "forzar": forzar,
        },
        resultado="ok" if (ok_1 or ok_2 or ok_3) else "error",
        detalle=f"Se inició oferta de agregados por WhatsApp. Origen: {origen}.",
        procesado=True,
    )

    return bool(ok_1 or ok_2 or ok_3)


def wa_procesar_respuesta_cross_sell(pedido, texto_cliente, sku_actual, indice_actual):
    
    tel = normalizar_telefono_service(pedido.telefono)
    productos = obtener_productos_a_ofrecer(pedido)

    if _es_consulta_factura(texto_cliente):
        return _responder_factura_o_escalar(pedido, texto_cliente)
    if _es_queja_o_problema(texto_cliente):
        _escalar_operador(pedido, "Queja durante cross-sell", "Te derivamos con un operador para ayudarte mejor.")
        return
    if _pregunta_precio(texto_cliente) or _es_afirmativo(texto_cliente):
        cantidad = _pregunta_cantidad(texto_cliente) or 1

        wa_escalar_venta_cerrada(
            pedido,
            sku_actual,
            cantidad,
            operador_notificado=True,
        )

        pedido.ia_requiere_operador = True

        _guardar_estado_wa(
            pedido,
            f"cross_sell:{sku_actual}:cliente_interesado:{cantidad}",
            tel,
        )

        wa_enviar_texto(
            tel,
            "Perfecto, te confirmamos con un operador cómo agregarlo al pedido.",
            pedido=pedido,
            autor="bot",
        )

        return
    if _es_negativo(texto_cliente):
        siguiente_idx = indice_actual + 1
        if siguiente_idx < len(productos):
            siguiente_sku = productos[siguiente_idx]
            _guardar_estado_wa(pedido, f"cross_sell:{siguiente_sku}:{siguiente_idx}", tel)
            wa_ofrecer_producto(tel, siguiente_sku)
        else:
            wa_cerrar_cross_sell(tel)
            _guardar_estado_wa(pedido, WA_CROSS_SELL_CERRADO, tel)
        return
    _wa_responder_con_ia(pedido, texto_cliente, tel)


# ─────────────────────────────────────────────
# IA fallback
# ─────────────────────────────────────────────

def _wa_responder_con_ia(pedido, texto_cliente, tel):
    if _es_consulta_factura(texto_cliente):
        return _responder_factura_o_escalar(pedido, texto_cliente)
    try:
        from app import ia_llamar_openai_chat
        prompt = f"""
Sos el asistente de atención al cliente de Fierro 100% Argento.
Respondé breve, amable y en español rioplatense.

Estado del pedido: {pedido.estado or 'En proceso'}
Empresa de envío: {pedido.empresa_envio or 'No asignada'}
Tipo de entrega: {pedido.tipo_entrega or 'No asignada'}

Mensaje del cliente: """ + "\"\"\"" + f"{texto_cliente}" + "\"\"\"" + """

REGLAS:
- No informes costos de envío. Para el cliente es envío sin cargo.
- No menciones factura, facturación, factura A/B ni datos fiscales si el cliente no preguntó específicamente por eso.
- Si pregunta por factura A/B: decir que sí, y que se emite con los datos cargados en la plataforma.
- Si necesita factura con datos distintos, reclamo, queja, cancelación o algo riesgoso: respondé que lo deriva un operador y agregá exactamente ESCALAR.
- Nunca prometas fecha exacta de entrega.
- Respondé solo el mensaje para el cliente.
"""
        respuesta = ia_llamar_openai_chat(prompt)
        if "ESCALAR" in (respuesta or ""):
            respuesta = respuesta.replace("ESCALAR", "").strip()
            _escalar_operador(pedido, f"IA no pudo resolver: {texto_cliente[:80]}")
        if respuesta:
            wa_enviar_texto(tel, respuesta)
    except Exception as e:
        print("[WA] Error IA:", e)
        _escalar_operador(pedido, "Error IA", "Te derivamos con un operador para ayudarte mejor.")
