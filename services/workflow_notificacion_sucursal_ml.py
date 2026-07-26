"""
Notificación ML posterior a una sucursal detectada.

Compone:
- respuesta neutra para consultas de horarios;
- transición ML centralizada;
- marca de consulta secundaria;
- intento de WhatsApp/cross-sell.

No importa app.py.
"""

from dataclasses import dataclass
from typing import Any, Callable

from services.ml_sucursal_cross_sell_guard import (
    intentar_wa_cross_sell_tras_sucursal_ml,
)
from services.sucursal_consulta_mixta import (
    agregar_respuesta_neutra_horarios_retiro,
    marcar_consulta_horarios_retiro_pendiente,
)
from services.workflow_transicion_sucursal_ml import (
    ejecutar_transicion_ml_tras_confirmacion_sucursal,
)


@dataclass(frozen=True)
class ResultadoNotificacionSucursalML:
    estado: str
    mensaje: str = ""
    motivo: str = ""
    transicion: Any = None
    consulta_marcada: bool = False
    cross_sell: Any = None
    error_consulta: str = ""
    error_cross_sell: str = ""

    @property
    def respuesta_flujo(self):
        if self.estado == "omitida":
            return False, self.motivo
        return None

    @property
    def notificada(self) -> bool:
        return self.estado == "notificada"


def _construir_mensaje_confirmacion(
    pedido: Any,
    sucursal: dict[str, Any],
) -> str:
    nombre_cliente = (
        str(
            getattr(pedido, "cliente", "")
            or "Cliente"
        ).split()[0]
        or "Cliente"
    )

    return (
        f"Muchas gracias {nombre_cliente}! 🙌\n\n"
        "Tu pedido ya está en proceso de despacho a:\n"
        f"📍 {sucursal.get('nombre')}\n"
        f"📌 {sucursal.get('direccion')}\n\n"
        "En breve te pasamos el número de seguimiento "
        "para que puedas rastrear tu envío 😊"
    )


def notificar_sucursal_detectada_ml(
    *,
    pedido: Any,
    sucursal: dict[str, Any] | None,
    texto_cliente: Any,
    puede_enviar_fn: Callable[..., Any],
    enviar_mensaje_fn: Callable[..., Any],
    registrar_envio_fn: Callable[..., Any],
    wa_auto_iniciar_fn: Callable[..., Any],
    db_session: Any,
    log_fn: Callable[[str], Any] = print,
) -> ResultadoNotificacionSucursalML:
    if not pedido or not sucursal:
        return ResultadoNotificacionSucursalML(
            estado="no_aplica",
            motivo="sin_pedido_o_sucursal",
        )

    mensaje = _construir_mensaje_confirmacion(
        pedido,
        sucursal,
    )

    try:
        mensaje = (
            agregar_respuesta_neutra_horarios_retiro(
                mensaje,
                texto_cliente,
            )
        )
    except Exception as error:
        log_fn(
            "[SUCURSAL] No se pudo agregar respuesta "
            f"neutra por horarios: {error}"
        )

    transicion = (
        ejecutar_transicion_ml_tras_confirmacion_sucursal(
            pedido=pedido,
            texto=mensaje,
            puede_enviar_fn=puede_enviar_fn,
            enviar_mensaje_fn=enviar_mensaje_fn,
            registrar_envio_fn=registrar_envio_fn,
            continuar_si_motivo_repetido=True,
            log_fn=log_fn,
        )
    )

    if transicion.omitida:
        return ResultadoNotificacionSucursalML(
            estado="omitida",
            mensaje=mensaje,
            motivo=transicion.motivo,
            transicion=transicion,
        )

    if transicion.estado == "error":
        log_fn(
            "[VIA CARGO] No se pudo enviar "
            "confirmación de sucursal pedido "
            f"#{getattr(pedido, 'id', '')}: "
            f"{transicion.motivo}"
        )
        return ResultadoNotificacionSucursalML(
            estado="error",
            mensaje=mensaje,
            motivo=transicion.motivo,
            transicion=transicion,
        )

    consulta_marcada = False
    error_consulta = ""

    try:
        consulta_marcada = bool(
            marcar_consulta_horarios_retiro_pendiente(
                pedido,
                texto_cliente,
            )
        )
    except Exception as error:
        error_consulta = str(error)
        log_fn(
            "[SUCURSAL] No se pudo marcar "
            f"consulta secundaria: {error}"
        )

    cross_sell = None
    error_cross_sell = ""

    try:
        cross_sell = (
            intentar_wa_cross_sell_tras_sucursal_ml(
                pedido,
                wa_auto_iniciar_desde_ml_fn=(
                    wa_auto_iniciar_fn
                ),
                db_session=db_session,
                motivo="sucursal_confirmada_ml",
                log_error_fn=lambda error: log_fn(
                    "[WA-AUTO-ML] Error iniciando "
                    "WA/cross-sell tras sucursal "
                    f"pedido #{getattr(pedido, 'id', '')}: "
                    f"{error}"
                ),
            )
        )
    except Exception as error:
        error_cross_sell = str(error)
        log_fn(
            "[VIA CARGO] No se pudo completar "
            "post-confirmación de sucursal pedido "
            f"#{getattr(pedido, 'id', '')}: "
            f"{error}"
        )

    return ResultadoNotificacionSucursalML(
        estado="notificada",
        mensaje=mensaje,
        motivo="notificada",
        transicion=transicion,
        consulta_marcada=consulta_marcada,
        cross_sell=cross_sell,
        error_consulta=error_consulta,
        error_cross_sell=error_cross_sell,
    )
