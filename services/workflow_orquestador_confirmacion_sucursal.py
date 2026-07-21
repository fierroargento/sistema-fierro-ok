"""
Orquestación completa de confirmación de sucursal.

Compone los servicios especializados, pero recibe por
inyección todas las dependencias externas de app.py.
"""

from dataclasses import dataclass
from typing import Any, Callable

from services.workflow_confirmacion_sucursal import (
    resolver_confirmacion_sucursal_via_cargo_ofrecida,
)
from services.workflow_finalizacion_confirmacion_sucursal import (
    finalizar_confirmacion_sucursal_persistida,
)
from services.workflow_persistencia_confirmacion_sucursal import (
    ejecutar_estado_y_persistencia_post_confirmacion,
)
from services.workflow_post_confirmacion_sucursal import (
    FLUJO_CONFIRMACION_COMUN_ML,
    FLUJO_CONFIRMACION_TEMPRANA,
    planificar_post_confirmacion_sucursal,
)
from services.workflow_transicion_sucursal_ml import (
    ejecutar_transicion_ml_tras_confirmacion_sucursal,
)


@dataclass(frozen=True)
class ResultadoOrquestacionConfirmacionSucursal:
    confirmacion: Any
    plan: Any
    persistencia: Any
    transicion_ml: Any = None
    finalizacion: Any = None

    @property
    def confirmada(self) -> bool:
        return bool(
            getattr(self.confirmacion, "confirmada", False)
        )

    @property
    def persistida(self) -> bool:
        return bool(
            getattr(self.persistencia, "exitosa", False)
        )

    @property
    def finalizada(self) -> bool:
        return bool(
            getattr(self.finalizacion, "finalizada", False)
        )

    @property
    def respuesta_flujo(self) -> Any:
        respuesta = getattr(
            self.finalizacion,
            "respuesta_flujo",
            None,
        )
        if isinstance(respuesta, dict):
            return dict(respuesta)
        return respuesta


def orquestar_confirmacion_sucursal_temprana(
    pedido: Any,
    texto_cliente: Any,
    *,
    despacho_completo_fn: Callable[[Any], Any],
    actualizar_estado_fn: Callable[[Any], Any],
    db_session: Any,
    es_afirmativo_fn: Callable[[Any], bool] | None = None,
    log_fn: Callable[[str], Any] = print,
) -> ResultadoOrquestacionConfirmacionSucursal:
    confirmacion = (
        resolver_confirmacion_sucursal_via_cargo_ofrecida(
            pedido,
            texto_cliente,
            despacho_completo_fn=despacho_completo_fn,
            es_afirmativo_fn=es_afirmativo_fn,
            log_fn=log_fn,
        )
    )

    plan = planificar_post_confirmacion_sucursal(
        resultado_confirmacion=confirmacion,
        pedido=pedido,
        flujo=FLUJO_CONFIRMACION_TEMPRANA,
    )

    persistencia = (
        ejecutar_estado_y_persistencia_post_confirmacion(
            pedido=pedido,
            plan=plan,
            actualizar_estado_fn=actualizar_estado_fn,
            db_session=db_session,
            log_fn=log_fn,
        )
    )

    return ResultadoOrquestacionConfirmacionSucursal(
        confirmacion=confirmacion,
        plan=plan,
        persistencia=persistencia,
    )


def orquestar_confirmacion_sucursal_comun_ml(
    pedido: Any,
    texto_cliente: Any,
    *,
    despacho_completo_fn: Callable[[Any], Any],
    actualizar_estado_fn: Callable[[Any], Any],
    db_session: Any,
    puede_enviar_fn: Callable[..., Any],
    enviar_mensaje_fn: Callable[..., Any],
    registrar_envio_fn: Callable[..., Any],
    intentar_cross_sell_fn: Callable[..., Any],
    wa_auto_iniciar_fn: Callable[..., Any],
    es_afirmativo_fn: Callable[[Any], bool] | None = None,
    log_fn: Callable[[str], Any] = print,
) -> ResultadoOrquestacionConfirmacionSucursal:
    confirmacion = (
        resolver_confirmacion_sucursal_via_cargo_ofrecida(
            pedido,
            texto_cliente,
            despacho_completo_fn=despacho_completo_fn,
            es_afirmativo_fn=es_afirmativo_fn,
            log_fn=log_fn,
        )
    )

    plan = planificar_post_confirmacion_sucursal(
        resultado_confirmacion=confirmacion,
        pedido=pedido,
        flujo=FLUJO_CONFIRMACION_COMUN_ML,
    )

    transicion_ml = None
    if (
        plan.confirmada
        and plan.evaluar_transicion_ml
    ):
        transicion_ml = (
            ejecutar_transicion_ml_tras_confirmacion_sucursal(
                pedido=pedido,
                texto=plan.mensaje_transicion_ml,
                puede_enviar_fn=puede_enviar_fn,
                enviar_mensaje_fn=enviar_mensaje_fn,
                registrar_envio_fn=registrar_envio_fn,
                log_fn=log_fn,
            )
        )

    persistencia = (
        ejecutar_estado_y_persistencia_post_confirmacion(
            pedido=pedido,
            plan=plan,
            actualizar_estado_fn=actualizar_estado_fn,
            db_session=db_session,
            log_fn=log_fn,
        )
    )

    finalizacion = (
        finalizar_confirmacion_sucursal_persistida(
            pedido=pedido,
            plan=plan,
            resultado_persistencia=persistencia,
            intentar_cross_sell_fn=intentar_cross_sell_fn,
            wa_auto_iniciar_fn=wa_auto_iniciar_fn,
            db_session=db_session,
            log_fn=log_fn,
        )
    )

    return ResultadoOrquestacionConfirmacionSucursal(
        confirmacion=confirmacion,
        plan=plan,
        transicion_ml=transicion_ml,
        persistencia=persistencia,
        finalizacion=finalizacion,
    )
