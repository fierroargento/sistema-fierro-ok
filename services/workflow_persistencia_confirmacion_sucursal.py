"""
Estado y persistencia posteriores a confirmar sucursal.

No envía mensajes.
No decide canal.
No ejecuta cross-sell.
"""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ResultadoPersistenciaConfirmacionSucursal:
    estado: str
    estado_actualizado: bool = False
    persistencia_realizada: bool = False
    motivo: str = ""

    @property
    def exitosa(self) -> bool:
        return self.estado in {
            "persistida",
            "aplicada_sin_persistencia",
        }


def ejecutar_estado_y_persistencia_post_confirmacion(
    *,
    pedido: Any,
    plan: Any,
    actualizar_estado_fn: Callable[[Any], Any],
    db_session: Any,
    log_fn: Callable[[str], None] = print,
) -> ResultadoPersistenciaConfirmacionSucursal:
    """
    Actualiza estado y persiste según el plan.

    Un error actualizando estado no invalida la confirmación.
    Un error persistiendo hace rollback y devuelve error.
    """

    if not plan or not bool(
        getattr(plan, "confirmada", False)
    ):
        return ResultadoPersistenciaConfirmacionSucursal(
            estado="no_aplica",
            motivo="sin_confirmacion",
        )

    estado_actualizado = False
    motivo_estado = ""

    if bool(
        getattr(plan, "actualizar_estado", False)
    ):
        try:
            actualizar_estado_fn(pedido)
            estado_actualizado = True
        except Exception as error:
            motivo_estado = (
                "error_actualizando_estado:"
                f"{error}"
            )
            log_fn(
                "[VIA CARGO] No se pudo "
                "autoactualizar estado tras sucursal: "
                f"{error}"
            )

    if not bool(
        getattr(plan, "persistir", False)
    ):
        return ResultadoPersistenciaConfirmacionSucursal(
            estado="aplicada_sin_persistencia",
            estado_actualizado=estado_actualizado,
            persistencia_realizada=False,
            motivo=motivo_estado,
        )

    try:
        db_session.commit()
    except Exception as error:
        try:
            db_session.rollback()
        except Exception as rollback_error:
            log_fn(
                "[VIA CARGO] Error haciendo rollback "
                "tras fallar persistencia de sucursal: "
                f"{rollback_error}"
            )

        log_fn(
            "[VIA CARGO] No se pudo persistir "
            "confirmacion de sucursal: "
            f"{error}"
        )

        return ResultadoPersistenciaConfirmacionSucursal(
            estado="error_persistencia",
            estado_actualizado=estado_actualizado,
            persistencia_realizada=False,
            motivo=str(error),
        )

    return ResultadoPersistenciaConfirmacionSucursal(
        estado="persistida",
        estado_actualizado=estado_actualizado,
        persistencia_realizada=True,
        motivo=motivo_estado,
    )
