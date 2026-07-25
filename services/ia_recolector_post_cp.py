"""
Orquestación posterior a la aplicación de un código postal.

No depende de Flask ni app.py.
Recibe efectos externos por inyección.
"""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ResultadoPostCodigoPostal:
    confirmacion: Any = None
    persistida: bool = False
    finalizar_analisis: bool = False
    reenganche_intentado: bool = False
    reenganche_resultado: Any = None
    error_confirmacion: str = ""
    error_reenganche: str = ""


def procesar_post_codigo_postal_recolector(
    pedido,
    texto_logistica,
    *,
    orquestar_confirmacion_fn: Callable[..., Any],
    despacho_completo_fn: Callable[..., Any],
    actualizar_estado_fn: Callable[..., Any],
    db_session,
    es_afirmativo_fn: Callable[..., Any],
    auto_responder_fn: Callable[..., Any],
    logger_fn=print,
):
    """Confirma sucursal temprano o reengancha la automatización."""
    confirmacion = None
    error_confirmacion = ""

    try:
        resultado_orquestacion = (
            orquestar_confirmacion_fn(
                pedido,
                texto_logistica,
                despacho_completo_fn=(
                    despacho_completo_fn
                ),
                actualizar_estado_fn=(
                    actualizar_estado_fn
                ),
                db_session=db_session,
                es_afirmativo_fn=(
                    es_afirmativo_fn
                ),
            )
        )
        confirmacion = getattr(
            resultado_orquestacion,
            "confirmacion",
            None,
        )
        persistida = bool(
            getattr(
                resultado_orquestacion,
                "persistida",
                False,
            )
        )

        if persistida:
            return ResultadoPostCodigoPostal(
                confirmacion=confirmacion,
                persistida=True,
                finalizar_analisis=True,
            )

    except Exception as error:
        error_confirmacion = str(error)

        if logger_fn:
            logger_fn(
                "[VIA CARGO] No se pudo confirmar "
                "sucursal antes de auto-respuesta ML: "
                f"{error}"
            )

    try:
        resultado_reenganche = auto_responder_fn(
            pedido
        )

        return ResultadoPostCodigoPostal(
            confirmacion=confirmacion,
            persistida=False,
            finalizar_analisis=False,
            reenganche_intentado=True,
            reenganche_resultado=(
                resultado_reenganche
            ),
            error_confirmacion=(
                error_confirmacion
            ),
        )

    except Exception as error:
        if logger_fn:
            logger_fn(
                "[IA-CP-APB] No se pudo reenganchar "
                f"flujo pedido "
                f"#{getattr(pedido, 'id', '?')}: "
                f"{error}"
            )

        return ResultadoPostCodigoPostal(
            confirmacion=confirmacion,
            persistida=False,
            finalizar_analisis=False,
            reenganche_intentado=True,
            error_confirmacion=(
                error_confirmacion
            ),
            error_reenganche=str(error),
        )
