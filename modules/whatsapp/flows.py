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
from datetime import datetime

from .config import (
    WA_ESPERANDO_DATOS,
    WA_ESPERANDO_OK_INICIO,    
    WA_FALTA_ELEGIR_TRANSPORTE,
    WA_REQUIERE_OPERADOR,
    WA_CONFIRMADO_CLIENTE,
    WA_DESPACHO_EN_PROCESO,
    WA_DESPACHADO,
    WA_POSTVENTA,
    WA_FINALIZADO,
    WA_TEMPLATE_PEDIDO_DATO,
    WA_TEMPLATE_INICIO_DESPACHO,
    WA_TEMPLATE_INICIO_CHAT_OPERADOR,
    WA_TEMPLATE_SEGUIMIENTO,
    WA_TEMPLATE_RETIRO,
    WA_TEMPLATE_POSTVENTA_PARRILLA,    
)
from .sender import wa_enviar_texto, wa_enviar_template
from .cross_sell import (
    obtener_productos_a_ofrecer, wa_ofrecer_producto,
    wa_responder_precio, wa_cerrar_cross_sell, wa_escalar_venta_cerrada,
)


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
        pedido.wa_ultimo_contacto = datetime.utcnow()
        db.session.commit()
    except Exception as e:
        print("[WA] Error guardando estado:", e)


def _obtener_estado_wa(pedido):
    return str(getattr(pedido, "wa_estado", "") or "")


def _escalar_operador(pedido, motivo, mensaje_cliente=None):
    """Marca el pedido para atención humana sin romper ML."""
    try:
        from app import db, normalizar_telefono
        pedido.ml_mensajes_pendientes = True
        pedido.ml_mensajes_pendientes_count = (pedido.ml_mensajes_pendientes_count or 0) + 1
        pedido.ia_requiere_operador = True
        pedido.wa_estado = WA_REQUIERE_OPERADOR
        resumen_actual = (pedido.ia_resumen or "").strip()
        pedido.ia_resumen = f"{resumen_actual} | WA: {motivo}".strip(" |")
        pedido.wa_ultimo_contacto = datetime.utcnow()
        db.session.commit()
        print(f"[WA] Pedido #{pedido.id} escalado: {motivo}")

        if mensaje_cliente:
            tel = normalizar_telefono(pedido.telefono)
            if tel:
                wa_enviar_texto(tel, mensaje_cliente)
    except Exception as e:
        print("[WA] Error escalando:", e)


def _es_afirmativo(texto):
    texto = texto.lower().strip()
    return any(x in texto for x in [
        "si", "sí", "ok", "dale", "confirmo", "confirmado", "correcto",
        "exacto", "perfecto", "claro", "obvio", "de una", "va", "bueno",
        "está bien", "esta bien", "todo bien", "listo", "por supuesto",
    ])


def _es_negativo(texto):
    texto = texto.lower().strip()
    return any(x in texto for x in [
        "no", "nope", "negativo", "no gracias", "no me interesa", "no quiero",
        "paso", "por ahora no", "solo domicilio", "prefiero domicilio", "a domicilio",
    ])


def _pregunta_precio(texto):
    texto = texto.lower().strip()
    return any(x in texto for x in ["cuanto", "cuánto", "precio", "sale", "cuesta", "valor", "costo", "plata"])


def _pregunta_cantidad(texto):
    numeros = re.findall(r"\b([1-9][0-9]?)\b", texto)
    return int(numeros[0]) if numeros else None


def _es_queja_o_problema(texto):
    texto = texto.lower()
    return any(x in texto for x in [
        "reclamo", "queja", "problema", "no llegó", "no llego", "no recibi",
        "no recibí", "cancelar", "cancelación", "devolucion", "devolución",
        "estafa", "mentira", "mal", "roto", "defecto", "incompleto",
        "no funciona", "tarde", "demora", "donde esta", "dónde está",
    ])


def _es_consulta_factura(texto):
    t = texto.lower()
    return any(x in t for x in ["factura", "facturacion", "facturación", "factura a", "factura b"])


def _requiere_factura_distinta(texto):
    t = texto.lower()
    return any(x in t for x in [
        "otros datos", "otro dato", "otra razon", "otra razón", "razon social", "razón social",
        "otro cuit", "cuit distinto", "a nombre de", "datos distintos", "cambiar datos",
        "no son esos", "con estos datos", "te paso los datos",
    ])


def _responder_factura_o_escalar(pedido, texto_cliente):
    from app import normalizar_telefono
    tel = normalizar_telefono(pedido.telefono)
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

    from app import normalizar_telefono

    tel = normalizar_telefono(pedido.telefono)

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
    from app import normalizar_telefono

    tel = normalizar_telefono(pedido.telefono)
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
                "esperando_datos"
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
    from app import normalizar_telefono, ia_faltantes_pedido

    tel = normalizar_telefono(pedido.telefono)
    if not tel:
        return False

    faltantes = ia_faltantes_pedido(pedido)

    if faltantes:
        return wa_enviar_solicitud_datos(pedido, faltantes)

    return wa_cerrar_datos_completos(pedido)

def wa_procesar_datos_recibidos(pedido, texto_cliente):
    from app import (
        normalizar_telefono, ia_analizar_datos_cliente_ml_acordas,
        ia_guardar_resultado_recolector, ia_faltantes_pedido,
        ia_datos_previos_pedido, db,
    )
    tel = normalizar_telefono(pedido.telefono)

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
    pedido.wa_ultimo_contacto = datetime.utcnow()
    db.session.commit()


def wa_cerrar_datos_completos(pedido):
    """Datos completos: para PP6040 prepara Correo y no informa costos al cliente."""
    from app import normalizar_telefono, db, actualizar_estado_conversacional, registrar_evento_operativo
    from modules.transportes.selector import pedido_contiene_pp6040, asignar_transporte_pedido, sugerir_sucursales_correo_pedido

    tel = normalizar_telefono(pedido.telefono)
    if not tel:
        return False

    actualizar_estado_conversacional(
        pedido,
        owner_actual="bot",
        canal_activo="wa",
        estado_conversacional="datos_completos",
        takeover_activo=False,
        bot_pausado=False,
    )

    registrar_evento_operativo(
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
        # Cotización interna y sucursales/puntos Correo.
        ok, msg = asignar_transporte_pedido(pedido, preferencia_cliente="sucursal")
        msg_suc = sugerir_sucursales_correo_pedido(pedido)
        if msg_suc:
            _guardar_estado_wa(pedido, WA_FALTA_ELEGIR_TRANSPORTE, tel)
            return wa_enviar_texto(tel, msg_suc)
        if ok:
            _guardar_estado_wa(pedido, WA_DESPACHO_EN_PROCESO, tel)
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
        _escalar_operador(pedido, msg or "No se pudo resolver transporte Correo")
        return False

    # APB: si el flujo WA cerró datos y ya hay transporte asignado, no dejamos
    # tipo_entrega vacío para Via Cargo/Correo. El helper central respeta si
    # carga/admin ya eligió Domicilio u otra opción.
    try:
        from app import aplicar_default_tipo_entrega
        if aplicar_default_tipo_entrega(pedido):
            db.session.commit()
    except Exception as e:
        print("[WA] No se pudo aplicar tipo_entrega por defecto:", e)

    _guardar_estado_wa(pedido, WA_DESPACHO_EN_PROCESO, tel)
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


# ─────────────────────────────────────────────
# FLUJO TRANSPORTE CORREO
# ─────────────────────────────────────────────

def _cargar_sucursales_ofrecidas(pedido):
    raw = getattr(pedido, "correo_sucursales_ofrecidas", None) or getattr(pedido, "ia_sucursales_ofrecidas", "") or ""
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def wa_procesar_eleccion_transporte(pedido, texto_cliente):
    from app import normalizar_telefono, db
    from modules.transportes.selector import asignar_transporte_pedido
    tel = normalizar_telefono(pedido.telefono)
    texto = (texto_cliente or "").strip().lower()

    if _es_consulta_factura(texto_cliente):
        return _responder_factura_o_escalar(pedido, texto_cliente)

    if any(x in texto for x in ["domicilio", "a casa", "mi casa", "entrega en casa"]):
        # Primero educa. Si el cliente ya lo expresó en negativo/firme, evaluar regla y escalar si corresponde.
        ok, msg = asignar_transporte_pedido(pedido, preferencia_cliente="domicilio")
        if ok:
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
            return
        _escalar_operador(
            pedido,
            msg or "Cliente pidió domicilio y requiere revisión",
            "Siempre recomendamos retiro en sucursal o punto Correo porque suele ser más ordenado y evita posibles demoras por visitas fallidas en domicilio.\n\nDe todas maneras, lo revisamos con un operador y te confirmamos."
        )
        return

    if _es_queja_o_problema(texto_cliente):
        _escalar_operador(pedido, "Consulta/problema en elección de transporte", "Te derivamos con un operador para ayudarte mejor.")
        return

    sucs = _cargar_sucursales_ofrecidas(pedido)
    m = re.search(r"\b([1-3])\b", texto)
    if m and sucs:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(sucs):
            suc = sucs[idx]
            if not (pedido.empresa_envio or "").strip():
                pedido.empresa_envio = "Vía Cargo"
                
            pedido.tipo_entrega = "Sucursal"
            pedido.sucursal_nombre = suc.get("nombre") or suc.get("name") or pedido.sucursal_nombre
            pedido.direccion = suc.get("direccion") or suc.get("address") or pedido.direccion
            pedido.localidad = suc.get("localidad") or suc.get("city") or pedido.localidad
            pedido.provincia = suc.get("provincia") or pedido.provincia
            pedido.wa_estado = WA_DESPACHO_EN_PROCESO
            pedido.wa_ultimo_contacto = datetime.utcnow()
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
        _escalar_operador(pedido, "Cliente confirmó sucursal sin indicar número claro", "Perfecto, lo revisamos y te confirmamos el despacho.")
        return

    _escalar_operador(pedido, f"Respuesta no clara sobre transporte: {texto_cliente[:120]}", "Lo revisamos con un operador para no cometer errores en el despacho.")


# ─────────────────────────────────────────────
# FLUJO COMPATIBLE: CONFIRMACIÓN SUCURSAL LEGACY
# ─────────────────────────────────────────────

def wa_enviar_confirmacion_sucursal(pedido):
    from app import normalizar_telefono
    tel = normalizar_telefono(pedido.telefono)
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
    _guardar_estado_wa(pedido, "esperando_confirmacion_sucursal", tel)
    return wa_enviar_texto(tel, texto)


def wa_procesar_respuesta_confirmacion(pedido, texto_cliente):
    from app import normalizar_telefono
    tel = normalizar_telefono(pedido.telefono)
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


# ─────────────────────────────────────────────
# CROSS-SELL
# ─────────────────────────────────────────────

def wa_iniciar_cross_sell(pedido):
    from app import normalizar_telefono, actualizar_estado_conversacional, registrar_evento_operativo

    tel = normalizar_telefono(pedido.telefono)
    productos = obtener_productos_a_ofrecer(pedido)

    if not productos or not tel:
        return

    empresa = str(getattr(pedido, "empresa_envio", "") or "").strip()
    tipo_entrega = str(getattr(pedido, "tipo_entrega", "") or "").strip()
    sucursal = str(getattr(pedido, "sucursal_nombre", "") or "").strip()

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

    wa_enviar_texto(tel, texto_operativo)

    wa_enviar_texto(
        tel,
        "Aprovecho también para mostrarte algunos accesorios que suelen agregar junto con este pedido 👇"
    )

    primer_sku = productos[0]

    actualizar_estado_conversacional(
        pedido,
        owner_actual="bot",
        canal_activo="wa",
        estado_conversacional="cross_sell",
        takeover_activo=False,
        bot_pausado=False,
        cross_sell_activo=True,
    )

    registrar_evento_operativo(
        pedido=pedido,
        tipo_evento="cross_sell_iniciado",
        origen="bot",
        canal="wa",
        owner="bot",
        estado_conversacional="cross_sell",
        payload={
            "primer_sku": primer_sku,
            "productos": productos,
            "empresa_envio": empresa,
            "tipo_entrega": tipo_entrega,
            "sucursal": sucursal,
        },
        resultado="ok",
        detalle="Se inició oferta de agregados por WhatsApp.",
        procesado=True,
    )

    _guardar_estado_wa(pedido, f"cross_sell:{primer_sku}:0", tel)
    wa_ofrecer_producto(tel, primer_sku)


def wa_procesar_respuesta_cross_sell(pedido, texto_cliente, sku_actual, indice_actual):
    from app import normalizar_telefono
    tel = normalizar_telefono(pedido.telefono)
    productos = obtener_productos_a_ofrecer(pedido)

    if _es_consulta_factura(texto_cliente):
        return _responder_factura_o_escalar(pedido, texto_cliente)
    if _es_queja_o_problema(texto_cliente):
        _escalar_operador(pedido, "Queja durante cross-sell", "Te derivamos con un operador para ayudarte mejor.")
        return
    if _pregunta_precio(texto_cliente) or _es_afirmativo(texto_cliente):
        cantidad = _pregunta_cantidad(texto_cliente) or 1
        wa_responder_precio(tel, sku_actual, cantidad)
        _guardar_estado_wa(pedido, f"cross_sell:{sku_actual}:precio_enviado:{cantidad}", tel)
        return
    if _es_negativo(texto_cliente):
        siguiente_idx = indice_actual + 1
        if siguiente_idx < len(productos):
            siguiente_sku = productos[siguiente_idx]
            _guardar_estado_wa(pedido, f"cross_sell:{siguiente_sku}:{siguiente_idx}", tel)
            wa_ofrecer_producto(tel, siguiente_sku)
        else:
            wa_cerrar_cross_sell(tel)
            _guardar_estado_wa(pedido, "cross_sell_cerrado", tel)
        return
    _wa_responder_con_ia(pedido, texto_cliente, tel)


# ─────────────────────────────────────────────
# DESPACHO / TRACKING / POSTVENTA
# ─────────────────────────────────────────────

def wa_enviar_numero_seguimiento(pedido):
    from app import normalizar_telefono

    tel = normalizar_telefono(pedido.telefono)
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

    try:
        from app import tracking_info_pedido

        tracking_info = tracking_info_pedido(pedido) or {}
        link = tracking_info.get("url") or ""

    except Exception:
        link = ""

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
    from app import normalizar_telefono, db

    tel = normalizar_telefono(pedido.telefono)
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
            pedido.wa_ultimo_contacto = datetime.utcnow()
            db.session.commit()
        except Exception:
            db.session.rollback()

    return ok


def wa_enviar_postventa(pedido):
    from app import normalizar_telefono, db
    tel = normalizar_telefono(pedido.telefono)
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
            pedido.wa_ultimo_contacto = datetime.utcnow()
            db.session.commit()
        except Exception:
            db.session.rollback()
    return ok


def wa_procesar_respuesta_postventa(pedido, texto_cliente):
    from app import normalizar_telefono
    tel = normalizar_telefono(pedido.telefono)
    if _es_queja_o_problema(texto_cliente):
        _escalar_operador(pedido, "Problema postventa", "Te derivamos con un operador para ayudarte mejor.")
        return
    if _es_afirmativo(texto_cliente) or "gracias" in texto_cliente.lower():
        wa_enviar_texto(tel, "Gracias a vos! Un placer.")
        return
    _wa_responder_con_ia(pedido, texto_cliente, tel)


# ─────────────────────────────────────────────
# RECORDATORIOS
# ─────────────────────────────────────────────

def wa_enviar_recordatorio_1(pedido):
    from app import normalizar_telefono

    tel = normalizar_telefono(pedido.telefono)
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
    from app import normalizar_telefono

    tel = normalizar_telefono(pedido.telefono)
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
