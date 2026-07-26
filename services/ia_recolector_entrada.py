"""
Preparación de entrada para el recolector IA de Mercado Libre.

Valida precondiciones, normaliza el mensaje comprador y registra
la respuesta sin importar app.py, Flask ni modelos.
"""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class EntradaRecolectorML:
    habilitada: bool = False
    motivo: str = ""
    mensaje_comprador: Any = None
    texto_ultimo: str = ""
    texto: str = ""


def preparar_entrada_recolector_ml(
    *,
    pedido: Any,
    mensajes: Any,
    seller_id: str = "",
    es_pedido_aplicable_fn: Callable[[Any], bool],
    preparar_mensaje_fn: Callable[..., Any],
    marcar_respuesta_fn: Callable[..., Any],
) -> EntradaRecolectorML:
    if not pedido:
        return EntradaRecolectorML(
            motivo="sin_pedido",
        )

    if not es_pedido_aplicable_fn(pedido):
        return EntradaRecolectorML(
            motivo="no_aplica",
        )

    if not getattr(
        pedido,
        "contacto_iniciado",
        False,
    ):
        return EntradaRecolectorML(
            motivo="sin_contacto",
        )

    mensaje_comprador = preparar_mensaje_fn(
        mensajes,
        seller_id=seller_id,
    )

    if not mensaje_comprador:
        return EntradaRecolectorML(
            motivo="sin_mensaje",
        )

    texto_ultimo = str(
        getattr(
            mensaje_comprador,
            "texto_ultimo",
            "",
        )
        or ""
    )
    texto = str(
        getattr(
            mensaje_comprador,
            "texto",
            "",
        )
        or ""
    )

    if texto:
        marcar_respuesta_fn(
            pedido,
            canal="mercadolibre",
            commit=False,
        )

    return EntradaRecolectorML(
        habilitada=True,
        mensaje_comprador=mensaje_comprador,
        texto_ultimo=texto_ultimo,
        texto=texto,
    )
