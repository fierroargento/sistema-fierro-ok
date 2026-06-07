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

        diferencia = (
            ahora - fecha_ultimo
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

from datetime import datetime, timedelta


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


def pedido_es_ml_acordas_via_cargo_ownership(pedido):
    """
    Regla de canal:
    Mercado Libre / Acordás la Entrega / Vía Cargo.
    """
    if not pedido:
        return False

    canal = str(getattr(pedido, "canal", "") or "").strip()
    ml_tipo = str(getattr(pedido, "ml_tipo", "") or "").strip()
    empresa_envio = _normalizar_simple(getattr(pedido, "empresa_envio", ""))

    return bool(
        canal == "Mercado Libre"
        and ml_tipo == "Acordás la Entrega"
        and "via" in empresa_envio
        and "cargo" in empresa_envio
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
    Bloquea inicio WA mientras ML todavía debe cerrar sucursal.

    Excepción:
    Si ML no responde pasado el plazo configurado, WA puede arrancar para destrabar.
    """
    return bool(
        ml_acordas_via_cargo_sin_sucursal(pedido)
        and not ml_acordas_via_cargo_puede_pasar_a_wa_por_no_respuesta(pedido)
    )


def ml_acordas_via_cargo_bloquea_cross_sell(pedido):
    """
    Bloquea cross-sell hasta que haya sucursal elegida.

    Aunque se habilite WA por falta de respuesta ML,
    cross-sell sigue bloqueado porque la logística todavía no está cerrada.
    """
    return ml_acordas_via_cargo_sin_sucursal(pedido)