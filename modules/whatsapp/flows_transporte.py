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
    WA_REQUIERE_OPERADOR,
    WA_TEMPLATE_INICIO_CHAT_OPERADOR,
)

from modules.whatsapp.sender import wa_enviar_texto
def _cargar_sucursales_ofrecidas(pedido):
    raw = getattr(pedido, "correo_sucursales_ofrecidas", None) or getattr(pedido, "ia_sucursales_ofrecidas", "") or ""
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []
    

def _aplicar_sucursal_pedido(pedido, sucursal):
    """
    APB logística:
    aplica al pedido la sucursal confirmada/elegida por el cliente.

    No decide la sucursal. Solo persiste una sucursal que ya fue elegida
    explícitamente por número o confirmada cuando era la única opción ofrecida.
    """
    if not isinstance(sucursal, dict):
        sucursal = {}

    if not (pedido.empresa_envio or "").strip():
        pedido.empresa_envio = "Vía Cargo"

    pedido.tipo_entrega = "Sucursal"

    pedido.sucursal_nombre = (
        sucursal.get("nombre")
        or sucursal.get("name")
        or pedido.sucursal_nombre
    )

    pedido.direccion = (
        sucursal.get("direccion")
        or sucursal.get("address")
        or pedido.direccion
    )

    pedido.localidad = (
        sucursal.get("localidad")
        or sucursal.get("city")
        or pedido.localidad
    )

    pedido.provincia = (
        sucursal.get("provincia")
        or sucursal.get("state")
        or pedido.provincia
    )


def _mensaje_despacho_en_proceso():
    return (
        "Perfecto, ya tenemos todo para avanzar con el despacho.\n\n"
        "En breve te pasamos los detalles del envío y el seguimiento."
    )


def _normalizar_texto_logistica(valor):
    texto = str(valor or "").strip().lower()
    reemplazos = {
        "\u00e1": "a",
        "\u00e9": "e",
        "\u00ed": "i",
        "\u00f3": "o",
        "\u00fa": "u",
        "\u00fc": "u",
        "\u00f1": "n",
    }
    for viejo, nuevo in reemplazos.items():
        texto = texto.replace(viejo, nuevo)
    return texto


def pedido_requiere_sucursal_via_cargo_pendiente(pedido):
    """
    APB Via Cargo:
    La sucursal confirmada es parte de la logistica obligatoria.

    Aplica a:
    - Mercado Libre Acordas + Via Cargo a sucursal.
    - Tienda Nube + Via Cargo, porque el cliente debe elegir sucursal por WA.
    """
    if not pedido:
        return False

    canal = _normalizar_texto_logistica(getattr(pedido, "canal", ""))
    tipo_ml = _normalizar_texto_logistica(getattr(pedido, "tipo_ml", ""))
    empresa = _normalizar_texto_logistica(getattr(pedido, "empresa_envio", ""))
    tipo_entrega = _normalizar_texto_logistica(getattr(pedido, "tipo_entrega", ""))
    sucursal = str(getattr(pedido, "sucursal_nombre", "") or "").strip()

    es_ml_acordas = canal == "mercado libre" and "acord" in tipo_ml
    es_tienda_nube = canal == "tienda nube"
    es_via_cargo = "via cargo" in empresa or "cargo" in empresa
    es_sucursal = "sucursal" in tipo_entrega

    requiere_ml = es_ml_acordas and es_via_cargo and es_sucursal
    requiere_tn = es_tienda_nube and es_via_cargo

    return bool((requiere_ml or requiere_tn) and not sucursal)


def _cargar_sucursales_via_cargo_candidatas(pedido, limite=3):
    cp = str(getattr(pedido, "codigo_postal", "") or "").strip()
    localidad = _normalizar_texto_logistica(getattr(pedido, "localidad", ""))
    provincia = _normalizar_texto_logistica(getattr(pedido, "provincia", ""))

    try:
        with open("via_cargo_sucursales.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print("[WA] No se pudieron cargar sucursales Via Cargo:", e)
        return []

    if not isinstance(data, list):
        return []

    def cp_sucursal(s):
        return str(s.get("cp") or "").strip()

    def localidad_sucursal(s):
        return _normalizar_texto_logistica(s.get("localidad") or s.get("city") or "")

    def provincia_sucursal(s):
        return _normalizar_texto_logistica(s.get("provincia") or s.get("state") or "")

    candidatas = []

    if cp:
        candidatas = [s for s in data if cp_sucursal(s) == cp]

    if not candidatas and localidad:
        candidatas = [
            s for s in data
            if localidad and localidad in localidad_sucursal(s)
        ]

    if not candidatas and provincia:
        candidatas = [
            s for s in data
            if provincia and provincia in provincia_sucursal(s)
        ]

    if not candidatas and cp.isdigit():
        cp_int = int(cp)
        candidatas = sorted(
            [s for s in data if cp_sucursal(s).isdigit()],
            key=lambda s: abs(int(cp_sucursal(s)) - cp_int)
        )

    return candidatas[:limite]


def _formatear_sucursal_opcion(idx, sucursal):
    nombre = (
        sucursal.get("nombre")
        or sucursal.get("name")
        or "Sucursal Vía Cargo"
    )
    direccion = (
        sucursal.get("direccion")
        or sucursal.get("address")
        or ""
    )
    localidad = (
        sucursal.get("localidad")
        or sucursal.get("city")
        or ""
    )

    partes = [f"{idx}) {nombre}"]
    if direccion:
        partes.append(direccion)
    if localidad:
        partes.append(localidad)

    return " - ".join(partes)


def wa_ofrecer_sucursales_via_cargo_pendientes(pedido, texto_cliente=None):
    """
    Ofrece sucursales por WhatsApp cuando el handoff ML -> WA llego sin
    sucursal confirmada.

    APB:
    - No manda al cliente a buscar en internet.
    - No cierra logistica.
    - No inicia cross-sell.
    """
    from modules.whatsapp.flows import _guardar_estado_wa

    tel = normalizar_telefono_service(getattr(pedido, "telefono", ""))
    if not tel:
        return False

    sucs = _cargar_sucursales_via_cargo_candidatas(pedido)

    if not sucs:
        pedido.ia_requiere_operador = True
        _guardar_estado_wa(pedido, WA_REQUIERE_OPERADOR, tel)

        return wa_enviar_texto(
            tel,
            "Ya tengo tus datos para avanzar con el envío.\n\n"
            "Para no indicarte una sucursal incorrecta, lo revisa un operador "
            "y te confirmamos la sucursal de Vía Cargo más conveniente.",
            pedido=pedido,
        )

    pedido.ia_sucursales_ofrecidas = json.dumps(sucs, ensure_ascii=False)

    _guardar_estado_wa(
        pedido,
        WA_FALTA_ELEGIR_TRANSPORTE,
        tel
    )

    texto = (
        "Perfecto, el envío incluido es con retiro en sucursal Vía Cargo.\n\n"
        "Con los datos que me pasaste, encontramos estas opciones:\n\n"
    )

    texto += "\n".join(
        _formatear_sucursal_opcion(i + 1, suc)
        for i, suc in enumerate(sucs)
    )

    if len(sucs) == 1:
        texto += (
            "\n\nRespondeme *sí* si esa sucursal te queda bien, "
            "o avisame si querés que lo revise un operador."
        )
    else:
        texto += (
            "\n\nRespondeme con el número de la sucursal que preferís "
            "para dejar el despacho confirmado."
        )

    return wa_enviar_texto(
        tel,
        texto,
        pedido=pedido,
    )



def _cerrar_despacho_en_proceso_wa(pedido, tel, iniciar_cross_sell=False):
    """
    Cierra el flujo WA dejando el pedido en despacho en proceso.

    APB:
    - Centraliza el mismo cierre usado por varias ramas de transporte.
    - Evita mensajes duplicados y estados inconsistentes.
    - El cross-sell se inicia solo cuando la rama llamadora lo habilita.
    """
    from modules.whatsapp.flows import _guardar_estado_wa

    _guardar_estado_wa(
        pedido,
        WA_DESPACHO_EN_PROCESO,
        tel
    )

    wa_enviar_texto(
        tel,
        _mensaje_despacho_en_proceso(),
        pedido=pedido,
        fallback_template=WA_TEMPLATE_INICIO_CHAT_OPERADOR,
        fallback_parametros=[
            (getattr(pedido, "cliente", "") or "Cliente").split()[0],
            pedido.id_venta or pedido.id or "",
        ],
    )

    if iniciar_cross_sell:
        try:
            from modules.whatsapp.cross_sell_auto import intentar_cross_sell_automatico

            intentar_cross_sell_automatico(
                pedido,
                origen_disparo="wa_logistica_cerrada"
            )
        except Exception as e:
            print("[WA] Error intentando cross sell automático luego de cierre de despacho:", e)

    return True

    
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

        try:
            from modules.whatsapp.cross_sell_auto import intentar_cross_sell_automatico

            intentar_cross_sell_automatico(
                pedido,
                origen_disparo="wa_confirmacion_sucursal"
            )
        except Exception as e:
            print("[WA] Error intentando cross sell automático luego de confirmar sucursal:", e)

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
    )

    tel = normalizar_telefono_service(pedido.telefono)
    texto = (texto_cliente or "").strip().lower()

    if _es_consulta_factura(texto_cliente):
        return _responder_factura_o_escalar(pedido, texto_cliente)

    if pedido_requiere_sucursal_via_cargo_pendiente(pedido) and any(
        x in texto for x in ["domicilio", "a casa", "mi casa", "entrega en casa", "no es a domicilio"]
    ):
        return wa_ofrecer_sucursales_via_cargo_pendientes(
            pedido,
            texto_cliente=texto_cliente,
        )

    if pedido_requiere_sucursal_via_cargo_pendiente(pedido) and any(
        x in texto for x in ["donde", "via cargo", "sucursal", "cerca"]
    ):
        return wa_ofrecer_sucursales_via_cargo_pendientes(
            pedido,
            texto_cliente=texto_cliente,
        )

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

            _aplicar_sucursal_pedido(pedido, suc)
            _cerrar_despacho_en_proceso_wa(
                pedido,
                tel,
                iniciar_cross_sell=True
            )

            return

    if _es_afirmativo(texto) and sucs:
        if len(sucs) == 1:
            suc = sucs[0]

            try:
                _aplicar_sucursal_pedido(pedido, suc)
                _cerrar_despacho_en_proceso_wa(
                    pedido,
                    tel,
                    iniciar_cross_sell=True
                )
            except Exception as e:
                db.session.rollback()
                print("[WA] Error cerrando sucursal única confirmada:", e)

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

    tel = normalizar_telefono_service(pedido.telefono)

    if not tel:
        return False

    if pedido_requiere_sucursal_via_cargo_pendiente(pedido):
        return wa_ofrecer_sucursales_via_cargo_pendientes(pedido)

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

        msg_suc = sugerir_sucursales_correo_pedido(pedido, canal_origen="wa")

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
    )\n