"""
Flujo compartido para aplicar el resultado del recolector.

Modifica el pedido mediante el aplicador central y, únicamente
cuando este lo solicita, ejecuta el handoff inyectado.

No hace commit directamente.
No importa app.
No conoce Flask ni SQLAlchemy.
"""

from dataclasses import dataclass
from typing import Any, Callable

from modules.bot_ml.billing import (
    parece_nickname_ml,
)
from services.ia_recolector_resultado import (
    ResultadoAplicacionRecolector,
    aplicar_resultado_recolector,
)
from services.logistica_defaults import (
    es_ml_acordas_entrega_service,
    pedido_es_plegable_pp6040_service,
)


@dataclass(frozen=True)
class ResultadoProcesamientoRecolector:
    aplicacion: ResultadoAplicacionRecolector
    handoff_intentado: bool
    handoff_ok: bool | None
    motivo_handoff: str


def procesar_resultado_recolector(
    pedido: Any,
    texto_cliente: Any,
    resultado: Any,
    *,
    iniciar_handoff_fn: (
        Callable[..., tuple[bool, str]]
        | None
    ) = None,
    motivo_handoff: str = (
        "procesar_resultado_recolector"
    ),
    aplicar_resultado_fn: Callable[
        ...,
        ResultadoAplicacionRecolector,
    ] = aplicar_resultado_recolector,
) -> ResultadoProcesamientoRecolector:
    aplicacion = aplicar_resultado_fn(
        pedido,
        texto_cliente,
        resultado,
        parece_nickname_fn=parece_nickname_ml,
        es_ml_acordas_entrega_fn=(
            es_ml_acordas_entrega_service
        ),
        pedido_es_plegable_pp6040_fn=(
            pedido_es_plegable_pp6040_service
        ),
    )

    if not aplicacion.iniciar_handoff:
        return ResultadoProcesamientoRecolector(
            aplicacion=aplicacion,
            handoff_intentado=False,
            handoff_ok=None,
            motivo_handoff="no_requerido",
        )

    if iniciar_handoff_fn is None:
        return ResultadoProcesamientoRecolector(
            aplicacion=aplicacion,
            handoff_intentado=False,
            handoff_ok=None,
            motivo_handoff="sin_ejecutor",
        )

    handoff_ok, motivo_resultado = iniciar_handoff_fn(
        pedido,
        faltantes=list(aplicacion.faltantes),
        motivo=motivo_handoff,
    )

    return ResultadoProcesamientoRecolector(
        aplicacion=aplicacion,
        handoff_intentado=True,
        handoff_ok=bool(handoff_ok),
        motivo_handoff=str(
            motivo_resultado or ""
        ),
    )
