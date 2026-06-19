"""
services/ml_sucursal_cross_sell_guard.py

Guardas APB para ML Acordás:
- después de confirmar sucursal por ML, intentar handoff WA/cross-sell;
- si falla, marcar pendiente operador;
- proteger autoavance Cargando Pedido -> Etiqueta Lista cuando falta cross-sell.
"""


MARCA_AUTOAVANCE_REVERTIDO = (
    "CROSS-SELL PENDIENTE: autoavance a Etiqueta Lista revertido; "
    "iniciar propuesta por WhatsApp o registrar excepción trazable."
)

PREFIJO_WA_PENDIENTE = "CROSS-SELL/WA pendiente tras confirmar sucursal ML: "
PREFIJO_WA_ERROR = "CROSS-SELL/WA error tras confirmar sucursal ML: "


def _agregar_marca_resumen_unica(pedido, marca, limite=1000):
    resumen = (getattr(pedido, "ia_resumen", "") or "").strip()
    if marca not in resumen:
        pedido.ia_resumen = f"{resumen} | {marca}".strip(" |")[:limite]
    return pedido.ia_resumen


def marcar_pendiente_wa_cross_sell_tras_sucursal_ml(
    pedido,
    motivo,
    db_session=None,
    error=False,
):
    """Marca intervención humana si no se pudo iniciar WA/cross-sell."""
    if not pedido:
        return ""

    pedido.ml_mensajes_pendientes = True
    pedido.ia_requiere_operador = True

    prefijo = PREFIJO_WA_ERROR if error else PREFIJO_WA_PENDIENTE
    marca = f"{prefijo}{motivo or 'wa_no_iniciado'}"
    _agregar_marca_resumen_unica(pedido, marca)

    if db_session is not None:
        db_session.commit()

    return marca


def intentar_wa_cross_sell_tras_sucursal_ml(
    pedido,
    wa_auto_iniciar_desde_ml_fn,
    db_session=None,
    motivo="sucursal_confirmada_ml",
    log_error_fn=None,
):
    """Intenta iniciar WA/cross-sell después de confirmar sucursal por ML.

    Devuelve dict estable para que app.py solo orqueste.
    """
    try:
        ok_wa, motivo_wa = wa_auto_iniciar_desde_ml_fn(
            pedido,
            faltantes=[],
            motivo=motivo,
        )

        if ok_wa:
            return {
                "ok": True,
                "motivo": motivo_wa,
                "marca": "",
            }

        marca = marcar_pendiente_wa_cross_sell_tras_sucursal_ml(
            pedido,
            motivo_wa or "wa_no_iniciado",
            db_session=db_session,
            error=False,
        )

        return {
            "ok": False,
            "motivo": motivo_wa or "wa_no_iniciado",
            "marca": marca,
        }

    except Exception as e:
        marca = marcar_pendiente_wa_cross_sell_tras_sucursal_ml(
            pedido,
            str(e),
            db_session=db_session,
            error=True,
        )

        if log_error_fn:
            log_error_fn(e)

        return {
            "ok": False,
            "motivo": str(e),
            "marca": marca,
        }


def debe_bloquear_autoavance_etiqueta_lista_por_cross_sell(
    pedido,
    estado_cargando,
    cross_sell_rule_fn,
    auto_enabled,
    manual_enabled,
    evento_operativo_model,
    log_error_fn=None,
):
    """Evalúa si debe bloquearse el autoavance desde Cargando Pedido."""
    if not pedido:
        return False

    if getattr(pedido, "estado", None) not in [estado_cargando, "Cargando Pedido"]:
        return False

    try:
        return bool(
            cross_sell_rule_fn(
                pedido,
                auto_enabled=auto_enabled,
                manual_enabled=manual_enabled,
                evento_operativo_model=evento_operativo_model,
            )
        )
    except Exception as e:
        if log_error_fn:
            log_error_fn(e)
        return False


def revertir_autoavance_etiqueta_lista_por_cross_sell(pedido, estado_anterior):
    """Vuelve el pedido al estado anterior y lo deja visible para operador/carga."""
    if not pedido:
        return None

    pedido.estado = estado_anterior
    pedido.ml_mensajes_pendientes = True
    pedido.ia_requiere_operador = True
    _agregar_marca_resumen_unica(pedido, MARCA_AUTOAVANCE_REVERTIDO)
    return estado_anterior


def aplicar_reversion_autoavance_si_corresponde(
    pedido,
    estado_anterior,
    estado_etiqueta_lista,
    bloquear_cross_sell,
):
    if (
        bloquear_cross_sell
        and getattr(pedido, "estado", None) == estado_etiqueta_lista
    ):
        return revertir_autoavance_etiqueta_lista_por_cross_sell(
            pedido,
            estado_anterior,
        )

    return None
