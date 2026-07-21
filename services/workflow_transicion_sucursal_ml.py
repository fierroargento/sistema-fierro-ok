"""
Ejecución de la transición ML tras confirmar sucursal.

Las dependencias externas se reciben por parámetro.
No hace commit.
No cambia estados.
No ejecuta cross-sell.
"""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ResultadoTransicionSucursalML:
    estado: str
    motivo: str = ""

    @property
    def enviada(self) -> bool:
        return self.estado == "enviada"

    @property
    def omitida(self) -> bool:
        return self.estado == "omitida"


def ejecutar_transicion_ml_tras_confirmacion_sucursal(
    *,
    pedido: Any,
    texto: str,
    puede_enviar_fn: Callable[..., Any],
    enviar_mensaje_fn: Callable[..., Any],
    registrar_envio_fn: Callable[..., Any],
    log_fn: Callable[[str], None] = print,
) -> ResultadoTransicionSucursalML:
    """
    Evalúa Canal Manager y ejecuta una transición ML.

    Conserva el orden:
    validar → enviar → registrar.
    """

    if not pedido:
        return ResultadoTransicionSucursalML(
            estado="no_aplica",
            motivo="sin_pedido",
        )

    texto = str(texto or "").strip()
    if not texto:
        return ResultadoTransicionSucursalML(
            estado="no_aplica",
            motivo="sin_texto",
        )

    try:
        permitido, motivo = puede_enviar_fn(
            pedido=pedido,
            canal="ml",
            texto=texto,
        )

        if not permitido:
            motivo = str(motivo or "")
            log_fn(
                "[CANAL-MANAGER] ML transicion WA "
                "omitida pedido "
                f"#{getattr(pedido, 'id', '')}: "
                f"{motivo}"
            )
            return ResultadoTransicionSucursalML(
                estado="omitida",
                motivo=motivo,
            )

        enviar_mensaje_fn(
            pedido,
            texto,
            permitir_requiere_operador=True,
        )
        registrar_envio_fn(
            pedido=pedido,
            canal="ml",
            texto=texto,
        )

        return ResultadoTransicionSucursalML(
            estado="enviada",
            motivo="enviada",
        )

    except Exception as error:
        log_fn(
            "[ML-WA] No se pudo enviar "
            "confirmacion/transicion WA pedido "
            f"#{getattr(pedido, 'id', '')}: "
            f"{error}"
        )
        return ResultadoTransicionSucursalML(
            estado="error",
            motivo=str(error),
        )
