"""
Orquestación del análisis común del recolector de Mercado Libre.

No importa app.py, Flask ni modelos. Todas las dependencias
externas se reciben por inyección.
"""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ResultadoFlujoComunRecolector:
    resultado: Any = None
    finalizada: bool = False
    respuesta_flujo: Any = None

    @property
    def respuesta_analisis(self) -> Any:
        if self.finalizada:
            return self.respuesta_flujo
        return self.resultado


def procesar_flujo_comun_recolector(
    *,
    pedido: Any,
    texto: Any,
    forzar: bool,
    hash_texto_fn: Callable[[Any], Any],
    datos_previos_fn: Callable[..., Any],
    parece_nickname_fn: Callable[[Any], bool],
    analizar_datos_fn: Callable[..., Any],
    procesar_resultado_fn: Callable[..., Any],
    iniciar_handoff_fn: Callable[..., Any],
    orquestar_confirmacion_fn: Callable[..., Any],
    despacho_completo_fn: Callable[..., Any],
    actualizar_estado_fn: Callable[..., Any],
    db_session: Any,
    puede_enviar_fn: Callable[..., Any],
    enviar_mensaje_fn: Callable[..., Any],
    registrar_envio_fn: Callable[..., Any],
    intentar_cross_sell_fn: Callable[..., Any],
    es_afirmativo_fn: Callable[..., Any],
    auto_responder_fn: Callable[..., Any],
    logger_fn: Callable[[str], Any] = print,
) -> ResultadoFlujoComunRecolector:
    if not texto:
        return ResultadoFlujoComunRecolector(
            finalizada=True,
        )

    hash_texto = hash_texto_fn(texto)
    hash_anterior = str(
        getattr(
            pedido,
            "ia_ultimo_mensaje_hash",
            "",
        )
        or ""
    )

    if not forzar and hash_texto == hash_anterior:
        return ResultadoFlujoComunRecolector(
            finalizada=True,
        )

    datos_previos = datos_previos_fn(
        pedido,
        parece_nickname_fn=parece_nickname_fn,
    )
    resultado = analizar_datos_fn(
        texto,
        datos_previos,
    )

    procesar_resultado_fn(
        pedido,
        texto,
        resultado,
        iniciar_handoff_fn=iniciar_handoff_fn,
    )

    try:
        resultado_orquestacion = (
            orquestar_confirmacion_fn(
                pedido,
                texto,
                despacho_completo_fn=(
                    despacho_completo_fn
                ),
                actualizar_estado_fn=(
                    actualizar_estado_fn
                ),
                db_session=db_session,
                puede_enviar_fn=puede_enviar_fn,
                enviar_mensaje_fn=enviar_mensaje_fn,
                registrar_envio_fn=registrar_envio_fn,
                intentar_cross_sell_fn=(
                    intentar_cross_sell_fn
                ),
                wa_auto_iniciar_fn=(
                    iniciar_handoff_fn
                ),
                es_afirmativo_fn=(
                    es_afirmativo_fn
                ),
            )
        )

        if resultado_orquestacion.finalizada:
            return ResultadoFlujoComunRecolector(
                resultado=resultado,
                finalizada=True,
                respuesta_flujo=(
                    resultado_orquestacion
                    .respuesta_flujo
                ),
            )

    except Exception as exc:
        logger_fn(
            "[VIA CARGO] No se pudo confirmar "
            "sucursal en flujo comun ML: "
            f"{exc}"
        )

    if resultado and resultado.get("ok"):
        auto_responder_fn(pedido)

    return ResultadoFlujoComunRecolector(
        resultado=resultado,
    )
