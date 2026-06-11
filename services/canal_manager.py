"""
services/canal_manager.py
─────────────────────────
Autoridad APB mínima para mensajes automáticos.

Objetivo:
- evitar spam,
- evitar loops,
- evitar duplicados,
- respetar ownership de canal,
- centralizar reglas mínimas de envío.
"""

import json
from datetime import datetime, timedelta, UTC

from domain.estados import Estado, ESTADOS_CERRADOS

# Cooldown anti-spam por defecto
COOLDOWN_MINUTOS = 30


def puede_enviar_mensaje(
    pedido,
    canal,
    texto,
):
    """
    Decide si un mensaje automático puede enviarse.

    Retorna:
    (True, motivo)  -> puede enviar
    (False, motivo) -> bloqueado
    """

    # ---------------------------------------------------
    # REGLA 1
    # WhatsApp tiene autoridad sobre ML
    # ---------------------------------------------------

    wa_estado = str(
        getattr(pedido, "wa_estado", "") or ""
    ).strip().lower()

    if canal == "ml" and wa_estado:
        return (
            False,
            f"WhatsApp activo ({wa_estado})"
        )

    # ---------------------------------------------------
    # REGLA 2
    # Anti-duplicación exacta
    # ---------------------------------------------------

    ultimo_texto = str(
        getattr(
            pedido,
            "ultimo_mensaje_automatico_texto",
            ""
        ) or ""
    ).strip()

    ultimo_canal = str(
        getattr(
            pedido,
            "ultimo_mensaje_automatico_canal",
            ""
        ) or ""
    ).strip().lower()

    if (
        ultimo_texto
        and ultimo_canal == canal
        and ultimo_texto == texto.strip()
    ):
        return (
            False,
            "Mensaje automático repetido"
        )

    # ---------------------------------------------------
    # REGLA 3
    # Cooldown anti-spam
    # ---------------------------------------------------

    fecha_ultimo = getattr(
        pedido,
        "ultimo_mensaje_automatico_fecha",
        None
    )

    if (
        fecha_ultimo
        and ultimo_canal == canal
    ):
        ahora = datetime.now(UTC)

        # APB fechas:
        # Algunas fechas internas vienen naive desde SQLAlchemy/Postgres,
        # pero este service usa datetime.now(UTC), que es aware.
        # Antes de restar, normalizamos fecha_ultimo a UTC aware.
        try:
            if getattr(fecha_ultimo, "tzinfo", None) is None:
                fecha_ultimo_cmp = fecha_ultimo.replace(tzinfo=UTC)
            else:
                fecha_ultimo_cmp = fecha_ultimo.astimezone(UTC)
        except Exception:
            fecha_ultimo_cmp = None

        if fecha_ultimo_cmp:
            diferencia = (
                ahora - fecha_ultimo_cmp
            )

            if diferencia < timedelta(
                minutes=COOLDOWN_MINUTOS
            ):
                return (
                    False,
                    f"Cooldown activo ({COOLDOWN_MINUTOS} min)"
                )

    return (
        True,
        "OK"
    )


def registrar_envio_automatico(
    pedido,
    canal,
    texto,
):
    """
    Guarda metadata del último mensaje automático.
    """

    try:
        pedido.ultimo_mensaje_automatico_texto = texto

        pedido.ultimo_mensaje_automatico_canal = canal

        pedido.ultimo_mensaje_automatico_fecha = (
            datetime.now(UTC)
        )

    except Exception as e:
        print(
            "[CANAL-MANAGER] Error registrando envío:",
            e
        )

def wa_automatismo_bloqueado_por_operador(pedido):
    """
    APB / SaaS:
    Devuelve True si el operador tomó la conversación y, por lo tanto,
    ningún automatismo WA debe enviar mensajes al cliente.

    Importante:
    - No borra datos.
    - No cambia estados.
    - Solo actúa como guard central para módulos automáticos.
    """
    wa_estado = str(
        getattr(pedido, "wa_estado", "") or ""
    ).strip().lower()

    if wa_estado == "operador_manual":
        return True

    return False

def wa_operador_tiene_toma_activa(pedido):
    """
    APB / SaaS:
    Devuelve True si el operador tomó actualmente la conversación de WhatsApp.

    Esta función NO cancela el flujo operativo.
    Solo sirve como guard para evitar automatismos conversacionales
    mientras el operador está a cargo.
    """
    return str(
        getattr(pedido, "wa_estado", "") or ""
    ).strip().lower() == "operador_manual"

def wa_puede_gobernar_timeout(pedido):
    """
    Devuelve True solo si WhatsApp
    es realmente el owner operativo
    del timeout del pedido.
    """

    canal = str(
        getattr(pedido, "ia_canal_activo", "") or ""
    ).strip().lower()

    wa_estado = str(
        getattr(pedido, "wa_estado", "") or ""
    ).strip()

    # APB:
    # Si el operador tomó la conversación,
    # ningún timeout automático de WA gobierna.
    if wa_operador_tiene_toma_activa(pedido):
        return False

    # APB:
    # Si el canal activo no es WhatsApp,
    # WA no gobierna.
    if canal not in ("whatsapp", "wa"):
        return False

    # APB:
    # Debe existir estado WA real.
    if not wa_estado:
        return False

    return True

def ml_puede_gobernar_timeout(pedido):
    """
    Devuelve True solo si Mercado Libre
    puede gobernar el timeout del pedido.

    APB:
    si WhatsApp ya tomó ownership,
    ML queda pasivo.
    """

    wa_estado = str(
        getattr(pedido, "wa_estado", "") or ""
    ).strip()

    if wa_estado:
        return False

    return True

def puede_hacer_handoff_ml_a_whatsapp(
    pedido
):
    """
    Decide si el pedido puede migrar
    automáticamente de ML a WhatsApp.

    Solo evalúa ownership/reglas APB.
    No ejecuta mensajes ni acciones.
    """

    if not pedido:
        return (
            False,
            "sin_pedido",
        )

    wa_estado = str(
        getattr(pedido, "wa_estado", "") or ""
    ).strip()

    # APB:
    # Nunca pisar un flujo WA existente.
    if wa_estado:
        return (
            False,
            "wa_ya_iniciado",
        )

    estado = str(
        getattr(pedido, "estado", "") or ""
    ).strip()

    if estado in ESTADOS_CERRADOS + [
        Estado.DESPACHADO,
    ]:
        return (
            False,
            "pedido_cerrado",
        )

    ml_order_status_actual = str(
        getattr(
            pedido,
            "ml_order_status",
            "",
        ) or ""
    ).lower().strip()

    if ml_order_status_actual in {
        "closed",
        "cancelled",
        "invalid",
        "delivered",
    }:
        return (
            False,
            "ml_cerrado",
        )

    return (
        True,
        "ok",
    )      




def _normalizar_simple(valor):
    return str(valor or "").strip().lower()


def _dt_naive_utc(valor):
    if not valor:
        return None

    try:
        if getattr(valor, "tzinfo", None) is not None:
            return valor.replace(tzinfo=None)
    except Exception:
        pass

    return valor


def _faltantes_recolector_pedido(pedido):
    """
    Devuelve la lista de faltantes reales del recolector ML.

    APB:
    No importa funciones de app.py.
    Lee el campo persistido pedido.ia_faltantes.
    """
    if not pedido:
        return []

    raw = getattr(pedido, "ia_faltantes", None)

    if not raw:
        return []

    if isinstance(raw, list):
        return [
            str(x or "").strip()
            for x in raw
            if str(x or "").strip()
        ]

    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [
                str(x or "").strip()
                for x in data
                if str(x or "").strip()
            ]
    except Exception:
        pass

    return []


def pedido_es_plegable_pp6040_ownership(pedido):
    """
    Detección simple y desacoplada de app.py.

    Se usa para reglas de ownership/canales, no para pricing ni catálogo.
    """
    if not pedido:
        return False

    for item in (getattr(pedido, "items", None) or []):
        sku = str(getattr(item, "sku", "") or "").upper().strip()
        descripcion = str(getattr(item, "descripcion", "") or "").upper().strip()

        if "PP6040" in sku or "PP6040" in descripcion or "PLEGABLE" in descripcion:
            return True

    return False

def pedido_es_ml_acordas_ownership(pedido):
    """
    Regla general de ownership:
    Mercado Libre / Acordás la Entrega.
    """
    if not pedido:
        return False

    canal = _normalizar_simple(getattr(pedido, "canal", ""))
    ml_tipo = _normalizar_simple(getattr(pedido, "ml_tipo", ""))

    return bool(
        canal == "mercado libre"
        and "acord" in ml_tipo
        and "entrega" in ml_tipo
    )


def pedido_es_ml_acordas_via_cargo_ownership(pedido):
    """
    Regla de canal APB:

    En Sistema Fierro, Mercado Libre / Acordás la Entrega / no PP6040
    debe cerrar sucursal antes de pasar a WhatsApp o cross-sell.

    Importante:
    No dependemos de empresa_envio acá, porque en el arranque del flujo
    ese campo puede estar vacío todavía. Operativamente, si es Acordás
    y no es PP6040, el camino esperado es Vía Cargo / sucursal.
    """
    if not pedido:
        return False

    canal = _normalizar_simple(getattr(pedido, "canal", ""))
    ml_tipo = _normalizar_simple(getattr(pedido, "ml_tipo", ""))

    es_mercado_libre = canal == "mercado libre"
    es_acordas_entrega = "acord" in ml_tipo and "entrega" in ml_tipo

    return bool(
        es_mercado_libre
        and es_acordas_entrega
    )


def ml_acordas_via_cargo_sin_sucursal(pedido):
    """
    Caso base:
    ML / Acordás / Vía Cargo / no PP6040 / sin sucursal elegida.
    """
    return bool(
        pedido_es_ml_acordas_via_cargo_ownership(pedido)
        and not pedido_es_plegable_pp6040_ownership(pedido)
        and not str(getattr(pedido, "sucursal_nombre", "") or "").strip()
    )


def ml_acordas_via_cargo_puede_pasar_a_wa_por_no_respuesta(
    pedido,
    horas_sin_respuesta=24,
):
    """
    Excepción APB:
    Si ML no responde durante X horas, se permite iniciar WA para destrabar.

    Esto NO habilita cross-sell.
    Solo habilita WA para continuar/cerrar la logística.
    """
    if not ml_acordas_via_cargo_sin_sucursal(pedido):
        return False

    ultimo_bot = _dt_naive_utc(getattr(pedido, "ia_ultimo_mensaje_bot", None))
    ultimo_cliente = _dt_naive_utc(getattr(pedido, "ia_ultimo_mensaje_cliente", None))

    if not ultimo_bot:
        return False

    if ultimo_cliente and ultimo_cliente >= ultimo_bot:
        return False

    try:
        horas_sin_respuesta = int(horas_sin_respuesta or 24)
    except Exception:
        horas_sin_respuesta = 24

    return datetime.utcnow() - ultimo_bot >= timedelta(hours=horas_sin_respuesta)


def ml_acordas_via_cargo_bloquea_inicio_wa(pedido):
    """
    Regla APB actualizada:
    la falta de sucursal Vía Cargo NO debe bloquear el inicio de WhatsApp.

    Motivo:
    - Si los datos básicos ya están completos, WhatsApp puede usarse para destrabar
      la elección de sucursal o continuar la coordinación.
    - La logística abierta sí debe seguir bloqueando cross-sell y avance operativo,
      pero eso lo controla ml_acordas_logistica_abierta_bloquea_cross_sell().
    """
    return False


def ml_acordas_logistica_abierta_bloquea_cross_sell(pedido):
    """
    APB Comercial:
    No se ofrece cross-sell si la logística todavía no está definida.

    Regla:
    Antes de vender agregados, el pedido debe estar encaminado.

    Cubre:
    - ML / Acordás con faltantes reales del recolector.
    - ML / Acordás / no PP6040 sin sucursal elegida.
    - ML / Acordás / PP6040 sin CP o sin transporte definido.
    - Consulta logística pendiente para operador mientras la logística no está cerrada.
    """
    if not pedido_es_ml_acordas_ownership(pedido):
        return False

    faltantes = _faltantes_recolector_pedido(pedido)
    if faltantes:
        return True

    es_pp6040 = pedido_es_plegable_pp6040_ownership(pedido)

    empresa_envio = str(
        getattr(pedido, "empresa_envio", "") or ""
    ).strip()

    sucursal = str(
        getattr(pedido, "sucursal_nombre", "") or ""
    ).strip()

    codigo_postal = str(
        getattr(pedido, "codigo_postal", "") or ""
    ).strip()

    # No PP6040: por regla operativa va por Vía Cargo / sucursal.
    # Sin sucursal elegida, la logística sigue abierta.
    if not es_pp6040 and not sucursal:
        return True

    # PP6040: no requiere sucursal Vía Cargo,
    # pero sí necesita CP y transporte definido para considerar logística encaminada.
    if es_pp6040:
        if not codigo_postal:
            return True

        if not empresa_envio:
            return True

    # Si hay consulta pendiente para operador y todavía no hay definición logística,
    # no corresponde mostrar cross-sell.
    requiere_operador = bool(
        getattr(pedido, "ia_requiere_operador", False)
        or str(getattr(pedido, "ia_recolector_estado", "") or "").strip() == "requiere_operador"
    )

    if requiere_operador and not empresa_envio and not sucursal:
        return True

    return False

def ml_acordas_via_cargo_bloquea_cross_sell(pedido):
    """
    Compatibilidad con módulos existentes.

    Antes bloqueaba solo ML/Acordás/no PP6040/sin sucursal.
    Ahora bloquea cualquier ML/Acordás con logística abierta.

    APB:
    Antes de vender agregados, la logística debe estar definida.
    """
    return ml_acordas_logistica_abierta_bloquea_cross_sell(pedido)

def pedido_puede_reencauzarse_a_ml(
    pedido,
    WhatsAppMensaje=None,
    EstadoConversacionalPedido=None,
):
    """
    APB / reparación de ownership:

    Devuelve True solo si el pedido parece estar contaminado con
    wa_estado='requiere_operador' sin WhatsApp real.

    Uso:
    - herramienta admin;
    - casos heredados/contaminados;
    - no forma parte del flujo operativo normal.

    Regla segura:
    - canal Mercado Libre;
    - wa_estado == requiere_operador;
    - sin mensajes WhatsApp reales;
    - sin canal conversacional WA real.
    """
    if not pedido:
        return False

    canal = str(
        getattr(pedido, "canal", "") or ""
    ).strip()

    if canal != "Mercado Libre":
        return False

    wa_estado = str(
        getattr(pedido, "wa_estado", "") or ""
    ).strip().lower()

    if wa_estado != "requiere_operador":
        return False

    if WhatsAppMensaje is not None:
        try:
            tiene_wa_real = (
                WhatsAppMensaje.query
                .filter_by(pedido_id=pedido.id)
                .first()
                is not None
            )

            if tiene_wa_real:
                return False

        except Exception:
            return False

    if EstadoConversacionalPedido is not None:
        try:
            estado_conv = (
                EstadoConversacionalPedido.query
                .filter_by(pedido_id=pedido.id)
                .first()
            )

            if estado_conv:
                canal_activo = str(
                    getattr(estado_conv, "canal_activo", "") or ""
                ).strip().lower()

                # Si el canal activo real es WhatsApp, no se toca.
                if canal_activo in ("wa", "whatsapp"):
                    return False

        except Exception:
            return False

    return True


def devolver_conversacion_a_ml(
    pedido,
    WhatsAppMensaje=None,
    EstadoConversacionalPedido=None,
    nota="",
):
    """
    Reencauza un pedido Mercado Libre contaminado por ownership WhatsApp.

    APB:
    - No borra datos.
    - No borra historial.
    - No cambia estado operativo del pedido.
    - No limpia si hubo WhatsApp real.
    - Deja trazabilidad en ia_resumen.
    """
    if not pedido:
        return False, "sin_pedido"

    if not pedido_puede_reencauzarse_a_ml(
        pedido,
        WhatsAppMensaje=WhatsAppMensaje,
        EstadoConversacionalPedido=EstadoConversacionalPedido,
    ):
        return False, "no_es_reencauce_seguro"

    try:
        pedido.wa_estado = ""
    except Exception:
        pass

    try:
        pedido.ia_canal_activo = "mercadolibre"
    except Exception:
        pass

    try:
        resumen = str(
            getattr(pedido, "ia_resumen", "") or ""
        ).strip()

        marca = "REENCAUCE: conversación devuelta a Mercado Libre por admin"

        nota = str(nota or "").strip()
        if nota:
            marca = f"{marca} ({nota[:80]})"

        if marca not in resumen:
            pedido.ia_resumen = f"{resumen} | {marca}".strip(" |")[:1000]

    except Exception:
        pass

    return True, "reencauzado_a_ml"    
