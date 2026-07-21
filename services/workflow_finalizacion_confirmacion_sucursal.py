"""
Finalización posterior a persistir una sucursal.

No hace commit.
No actualiza estados.
No envía mensajes directamente.
"""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ResultadoFinalizacionConfirmacionSucursal:
    estado: str
    cross_sell_intentado: bool = False
    cross_sell_resultado: Any = None
    motivo: str = ""

    @property
    def finalizada(self) -> bool:
        return self.estado == "finalizada"

    @property
    def respuesta_flujo(self) -> dict[str, Any] | None:
        if not self.finalizada:
            return None

        return {
            "ok": True,
            "estado": "sucursal_confirmada",
            "sucursal_confirmada": True,
        }


def finalizar_confirmacion_sucursal_persistida(
    *,
    pedido: Any,
    plan: Any,
    resultado_persistencia: Any,
    intentar_cross_sell_fn: Callable[..., Any],
    wa_auto_iniciar_fn: Callable[..., Any],
    db_session: Any,
    log_fn: Callable[[str], None] = print,
) -> ResultadoFinalizacionConfirmacionSucursal:
    """
    Ejecuta acciones permitidas después del commit.

    El error de cross-sell no invalida una sucursal que
    ya fue confirmada y persistida.
    """

    if not plan or not bool(
        getattr(plan, "confirmada", False)
    ):
        return ResultadoFinalizacionConfirmacionSucursal(
            estado="no_aplica",
            motivo="sin_confirmacion",
        )

    if not resultado_persistencia or not bool(
        getattr(
            resultado_persistencia,
            "exitosa",
            False,
        )
    ):
        return ResultadoFinalizacionConfirmacionSucursal(
            estado="no_finalizada",
            motivo="persistencia_no_exitosa",
        )

    if not bool(
        getattr(plan, "intentar_cross_sell", False)
    ):
        return ResultadoFinalizacionConfirmacionSucursal(
            estado="finalizada",
            cross_sell_intentado=False,
        )

    try:
        resultado_cross_sell = intentar_cross_sell_fn(
            pedido,
            wa_auto_iniciar_desde_ml_fn=(
                wa_auto_iniciar_fn
            ),
            db_session=db_session,
            motivo=str(
                getattr(
                    plan,
                    "motivo_cross_sell",
                    "",
                )
                or ""
            ),
        )

        return ResultadoFinalizacionConfirmacionSucursal(
            estado="finalizada",
            cross_sell_intentado=True,
            cross_sell_resultado=resultado_cross_sell,
        )

    except Exception as error:
        log_fn(
            "[CROSS-SELL-ML-WA] No se pudo "
            "iniciar WA tras sucursal confirmada: "
            f"{error}"
        )

        return ResultadoFinalizacionConfirmacionSucursal(
            estado="finalizada",
            cross_sell_intentado=True,
            motivo=str(error),
        )
