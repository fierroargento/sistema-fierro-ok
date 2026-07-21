"""
Planificación posterior a una confirmación de sucursal.

No modifica el pedido.
No hace commit.
No envía mensajes.
No ejecuta cross-sell.
"""

from dataclasses import dataclass
from typing import Any


FLUJO_CONFIRMACION_TEMPRANA = (
    "confirmacion_temprana"
)
FLUJO_CONFIRMACION_COMUN_ML = (
    "confirmacion_comun_ml"
)

MOTIVO_CROSS_SELL_TRAS_SUCURSAL = (
    "sucursal_confirmada_sin_auto_respuesta"
)


@dataclass(frozen=True)
class PlanPostConfirmacionSucursal:
    confirmada: bool
    actualizar_estado: bool = False
    persistir: bool = False
    detener_flujo: bool = False
    evaluar_transicion_ml: bool = False
    intentar_cross_sell: bool = False
    mensaje_transicion_ml: str = ""
    motivo_cross_sell: str = ""


def construir_mensaje_transicion_sucursal_ml(
    pedido: Any,
) -> str:
    nombre_cliente = (
        str(
            getattr(pedido, "cliente", "")
            or "Cliente"
        ).split()[0]
        or "Cliente"
    )
    sucursal = str(
        getattr(pedido, "sucursal_nombre", "")
        or ""
    ).strip()
    direccion = str(
        getattr(pedido, "direccion", "")
        or ""
    ).strip()

    return (
        f"Perfecto {nombre_cliente}, ya registramos "
        "la sucursal elegida.\n\n"
        f"Sucursal: {sucursal}\n"
        f"Direccion: {direccion}\n\n"
        "Ahora seguimos la preparacion por WhatsApp "
        "para terminar de coordinar el despacho."
    )


def planificar_post_confirmacion_sucursal(
    *,
    resultado_confirmacion: Any,
    pedido: Any,
    flujo: str,
) -> PlanPostConfirmacionSucursal:
    """
    Describe las acciones posteriores sin ejecutarlas.
    """

    if flujo not in {
        FLUJO_CONFIRMACION_TEMPRANA,
        FLUJO_CONFIRMACION_COMUN_ML,
    }:
        raise ValueError(
            "flujo_post_confirmacion_invalido"
        )

    confirmada = bool(
        resultado_confirmacion
        and getattr(
            resultado_confirmacion,
            "confirmada",
            False,
        )
    )

    if not confirmada:
        return PlanPostConfirmacionSucursal(
            confirmada=False,
        )

    if flujo == FLUJO_CONFIRMACION_TEMPRANA:
        return PlanPostConfirmacionSucursal(
            confirmada=True,
            actualizar_estado=True,
            persistir=True,
            detener_flujo=True,
        )

    return PlanPostConfirmacionSucursal(
        confirmada=True,
        actualizar_estado=True,
        persistir=True,
        detener_flujo=True,
        evaluar_transicion_ml=True,
        intentar_cross_sell=True,
        mensaje_transicion_ml=(
            construir_mensaje_transicion_sucursal_ml(
                pedido
            )
        ),
        motivo_cross_sell=(
            MOTIVO_CROSS_SELL_TRAS_SUCURSAL
        ),
    )
