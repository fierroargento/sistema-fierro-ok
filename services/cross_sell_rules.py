"""
services/cross_sell_rules.py
────────────────────────────
Reglas comunes para decidir si corresponde iniciar o exigir cross-sell.

APB / SaaS:
- La decisión de cross-sell no debe estar duplicada entre ML, WA,
  operador manual y flujos automáticos.
- Los canales solo deben encargarse del envío.
- La oportunidad comercial debe tratarse antes de Etiqueta Lista.
- Después de Etiqueta Lista no se inicia cross-sell automático nuevo,
  pero el operador puede dispararlo manualmente hasta antes de Despachado.
"""

from domain.estados import Estado


ESTADOS_BLOQUEAN_CROSS_SELL_AUTO_NUEVO = {
    Estado.ETIQUETA_LISTA,
    Estado.ETIQUETA_IMPRESA,
    Estado.EMBALADO,
    Estado.DESPACHADO,
    Estado.VERIFICAR_DESTINO,
    Estado.LISTO_RETIRAR,
    Estado.DEMORA,
    Estado.RECLAMO,
    Estado.NO_ENTREGADO,
    Estado.ENTREGADO,
    Estado.FINALIZADO,
    Estado.CANCELADO,
    Estado.RECLAMAR_ML,
}


ESTADOS_BLOQUEAN_CROSS_SELL_MANUAL = {
    Estado.DESPACHADO,
    Estado.VERIFICAR_DESTINO,
    Estado.LISTO_RETIRAR,
    Estado.DEMORA,
    Estado.RECLAMO,
    Estado.NO_ENTREGADO,
    Estado.ENTREGADO,
    Estado.FINALIZADO,
    Estado.CANCELADO,
    Estado.RECLAMAR_ML,
}


EVENTOS_CROSS_SELL_GESTIONADO = {
    "cross_sell_iniciado",
    "cross_sell_propuesta_operador_enviada",
    "cross_sell_ofrecido_sin_respuesta",
    "cross_sell_rechazado",
    "cross_sell_cerrado",
    "cross_sell_exceptuado",
    "cross_sell_sin_productos",
}


def pedido_en_etapa_sin_cross_sell_auto_nuevo(pedido):
    if not pedido:
        return True

    estado = getattr(pedido, "estado", None)
    return estado in ESTADOS_BLOQUEAN_CROSS_SELL_AUTO_NUEVO


def pedido_en_etapa_sin_cross_sell_manual(pedido):
    if not pedido:
        return True

    estado = getattr(pedido, "estado", None)
    return estado in ESTADOS_BLOQUEAN_CROSS_SELL_MANUAL


def _normalizar_texto_faltante(valor):
    return str(valor or "").strip().lower()


def _faltante_es_logistico(valor):
    """
    APB:
    La falta de elección logística no bloquea cross-sell.

    Cross-sell nace desde datos completos comerciales. Si falta sucursal,
    transporte, tipo de entrega, seguimiento o etiqueta, eso debe resolverse
    en el flujo logístico, pero no debe ocultar la opción comercial/manual.
    """
    texto = _normalizar_texto_faltante(valor)

    if not texto:
        return False

    palabras_logisticas = [
        "sucursal",
        "transporte",
        "tipo_entrega",
        "tipo entrega",
        "tipo de entrega",
        "empresa_envio",
        "empresa envio",
        "empresa de envio",
        "empresa de envío",
        "envio",
        "envío",
        "seguimiento",
        "etiqueta",
        "correo",
        "via cargo",
        "vía cargo",
        "andreani",
        "mercado envios",
        "mercado envíos",
        "datos de entrega",
        "datos entrega",
        "entrega",
        "direccion",
        "dirección",
        "domicilio",
        "calle",
        "altura",
        "codigo postal",
        "código postal",
        "cp",
        "localidad",
        "provincia",
    ]

    return any(palabra in texto for palabra in palabras_logisticas)


def _hay_faltante_comercial_real(valor):
    """
    Devuelve True si el faltante representa datos comerciales/personales
    necesarios para operar cross-sell.

    Si el faltante es logístico, no bloquea.
    """
    texto = _normalizar_texto_faltante(valor)

    if not texto:
        return False

    try:
        import json

        data = json.loads(texto)

        if isinstance(data, list):
            return any(
                _normalizar_texto_faltante(item)
                and not _faltante_es_logistico(item)
                for item in data
            )

        if isinstance(data, dict):
            return any(
                _normalizar_texto_faltante(k)
                and not _faltante_es_logistico(k)
                for k, v in data.items()
                if v
            )

    except Exception:
        pass

    return not _faltante_es_logistico(texto)


def pedido_tiene_datos_completos_para_cross_sell(pedido):
    """
    Regla mínima defensiva: cross-sell nace después de datos completos.

    No bloqueamos por logística pendiente: desde datos completos la instancia
    comercial debe iniciarse o quedar disponible para operador.
    """
    if not pedido:
        return False

    campos_faltantes = [
        getattr(pedido, "ia_faltantes", ""),
        getattr(pedido, "ia_campos_faltantes", ""),
        getattr(pedido, "ml_campos_faltantes", ""),
    ]

    return not any(
        _hay_faltante_comercial_real(valor)
        for valor in campos_faltantes
    )


def cross_sell_tiene_productos_configurados(pedido):
    """
    Devuelve True si el pedido tiene productos de cross-sell configurados.

    Import local para no acoplar el módulo a WhatsApp en import-time.
    """
    try:
        from modules.whatsapp.cross_sell import obtener_productos_a_ofrecer

        return bool(obtener_productos_a_ofrecer(pedido))
    except Exception as e:
        print("[CROSS-SELL-RULES] No se pudo evaluar productos configurados:", e)
        return False


def cross_sell_ya_gestionado(pedido, evento_operativo_model=None):
    """
    Devuelve True si la oportunidad comercial ya fue tratada.

    Gestionado significa: iniciado/ofrecido, propuesta manual enviada,
    rechazado, cerrado, exceptuado o sin productos.
    """
    if not pedido:
        return False

    wa_estado = str(getattr(pedido, "wa_estado", "") or "").strip().lower()
    ia_estado = str(getattr(pedido, "ia_recolector_estado", "") or "").strip().lower()

    if wa_estado.startswith("cross_sell:"):
        return True

    estados_gestionados = {
        "cross_sell",
        "cross_sell_cerrado",
        "wa_cross_sell_cerrado",
        "operador_manual",
    }

    if wa_estado in estados_gestionados or ia_estado == "cross_sell":
        return True

    pedido_id = getattr(pedido, "id", None)
    if not pedido_id or evento_operativo_model is None:
        return False

    try:
        evento = (
            evento_operativo_model.query
            .filter(
                evento_operativo_model.pedido_id == pedido_id,
                evento_operativo_model.tipo_evento.in_(EVENTOS_CROSS_SELL_GESTIONADO),
                evento_operativo_model.resultado == "ok",
            )
            .first()
        )

        return evento is not None

    except Exception as e:
        print(f"[CROSS-SELL-RULES] No se pudo verificar eventos pedido #{pedido_id}: {e}")
        return False


def motivo_bloqueo_cross_sell(
    pedido,
    modo="auto",
    auto_enabled=True,
    manual_enabled=True,
    forzar=False,
):
    """
    Devuelve "" si puede iniciar cross-sell.
    Devuelve un código si debe bloquearse.

    Importante:
    - La logística pendiente NO bloquea por sí sola.
    - Automático: solo antes de Etiqueta Lista.
    - Manual operador: hasta antes de Despachado.
    """
    modo = (modo or "auto").strip().lower()

    if not pedido:
        return "sin_pedido"

    if modo == "operador":
        if not manual_enabled and not forzar:
            return "cross_sell_manual_deshabilitado"

        if pedido_en_etapa_sin_cross_sell_manual(pedido):
            return "pedido_en_etapa_posterior"

    else:
        if not auto_enabled:
            return "cross_sell_auto_deshabilitado"

        if pedido_en_etapa_sin_cross_sell_auto_nuevo(pedido):
            return "pedido_en_etapa_posterior"

    if not pedido_tiene_datos_completos_para_cross_sell(pedido):
        return "datos_incompletos"

    if not cross_sell_tiene_productos_configurados(pedido):
        return "sin_productos_cross_sell"

    return ""


def puede_iniciar_cross_sell_pedido(
    pedido,
    modo="auto",
    auto_enabled=True,
    manual_enabled=True,
    forzar=False,
):
    return not motivo_bloqueo_cross_sell(
        pedido,
        modo=modo,
        auto_enabled=auto_enabled,
        manual_enabled=manual_enabled,
        forzar=forzar,
    )


def debe_bloquear_etiqueta_lista_por_cross_sell(
    pedido,
    auto_enabled=True,
    manual_enabled=True,
    evento_operativo_model=None,
):
    """
    Bloquea Cargando Pedido -> Etiqueta Lista si la oportunidad comercial
    todavía no fue tratada.

    Si automático no pudo, el operador debe disparar manual o dejar excepción.
    """
    if not pedido:
        return False

    if getattr(pedido, "estado", None) != Estado.CARGANDO:
        return False

    if not (auto_enabled or manual_enabled):
        return False

    if not pedido_tiene_datos_completos_para_cross_sell(pedido):
        return False

    if not cross_sell_tiene_productos_configurados(pedido):
        return False

    if cross_sell_ya_gestionado(
        pedido,
        evento_operativo_model=evento_operativo_model,
    ):
        return False

    return True