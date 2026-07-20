"""
Confirmación operativa de sucursales ofrecidas.

No hace commit.
No envía mensajes.
No decide canal ni cross-sell.
"""

from dataclasses import dataclass
from typing import Any

from services.ia_recolector_sync import (
    marcar_recolector_datos_completos,
)
from services.via_cargo_sucursales import (
    cargar_sucursales_via_cargo,
)
from services.workflow_logistica_sucursal import (
    aplicar_decision_sucursal_al_pedido,
)
from services.workflow_sucursal_decision import (
    decidir_sucursal_via_cargo_para_pedido,
)


@dataclass(frozen=True)
class ResultadoConfirmacionSucursal:
    estado: str
    motivo: str = ""
    requiere_operador: bool = False
    consulta_secundaria: bool = False
    decision: Any = None

    @property
    def confirmada(self) -> bool:
        return self.estado == "confirmada"


def resolver_confirmacion_sucursal_via_cargo_ofrecida(
    pedido,
    texto_cliente,
    *,
    despacho_completo_fn,
    es_afirmativo_fn=None,
    log_fn=print,
) -> ResultadoConfirmacionSucursal:
    """
    Resuelve y aplica una confirmación de sucursal Vía Cargo.

    Devuelve el resultado operativo completo para que el
    llamador decida persistencia, canal y acciones posteriores.
    """

    if not pedido:
        return ResultadoConfirmacionSucursal(
            estado="sin_confirmacion",
            motivo="sin_pedido",
        )

    if str(
        getattr(pedido, "sucursal_nombre", "")
        or ""
    ).strip():
        return ResultadoConfirmacionSucursal(
            estado="sin_confirmacion",
            motivo="sucursal_ya_confirmada",
        )

    texto_cliente = str(
        texto_cliente or ""
    ).strip()
    if not texto_cliente:
        return ResultadoConfirmacionSucursal(
            estado="sin_confirmacion",
            motivo="sin_texto",
        )

    try:
        sucursales = cargar_sucursales_via_cargo()
        if not sucursales:
            return ResultadoConfirmacionSucursal(
                estado="sin_confirmacion",
                motivo="sin_catalogo",
            )

        decision_sucursal = (
            decidir_sucursal_via_cargo_para_pedido(
                pedido=pedido,
                texto=texto_cliente,
                sucursales_catalogo=sucursales,
                es_afirmativo_fn=es_afirmativo_fn,
                log_error_fn=lambda error: log_fn(
                    "[VIA CARGO] Error usando decision "
                    "central sucursal "
                    f"pedido #{getattr(pedido, 'id', '')}: "
                    f"{error}"
                ),
            )
        )

        requiere_operador = bool(
            getattr(
                decision_sucursal,
                "requiere_operador",
                False,
            )
        )
        consulta_secundaria = bool(
            getattr(
                decision_sucursal,
                "consulta_secundaria",
                False,
            )
        )
        motivo = str(
            getattr(decision_sucursal, "motivo", "")
            or ""
        )

        if not decision_sucursal.seleccionada:
            return ResultadoConfirmacionSucursal(
                estado=(
                    "requiere_operador"
                    if requiere_operador
                    else "sin_confirmacion"
                ),
                motivo=motivo,
                requiere_operador=requiere_operador,
                consulta_secundaria=consulta_secundaria,
                decision=decision_sucursal,
            )

        if not aplicar_decision_sucursal_al_pedido(
            pedido,
            decision_sucursal,
            transporte="Vía Cargo",
        ):
            return ResultadoConfirmacionSucursal(
                estado="sin_confirmacion",
                motivo="aplicacion_rechazada",
                requiere_operador=requiere_operador,
                consulta_secundaria=consulta_secundaria,
                decision=decision_sucursal,
            )

        try:
            if despacho_completo_fn(pedido):
                marcar_recolector_datos_completos(
                    pedido,
                )
        except Exception:
            pass

        log_fn(
            f"[VIA CARGO] Pedido "
            f"#{getattr(pedido, 'id', '')}: "
            "sucursal confirmada antes de "
            "auto-respuesta ML"
        )

        return ResultadoConfirmacionSucursal(
            estado="confirmada",
            motivo=motivo,
            requiere_operador=requiere_operador,
            consulta_secundaria=consulta_secundaria,
            decision=decision_sucursal,
        )

    except Exception as error:
        log_fn(
            "[VIA CARGO] Error confirmando "
            "sucursal ofrecida "
            f"pedido #{getattr(pedido, 'id', '')}: "
            f"{error}"
        )
        return ResultadoConfirmacionSucursal(
            estado="error",
            motivo="error_confirmando_sucursal",
        )


def confirmar_sucursal_via_cargo_ofrecida_sin_persistir(
    pedido,
    texto_cliente,
    *,
    despacho_completo_fn,
    es_afirmativo_fn=None,
    log_fn=print,
):
    """
    Wrapper booleano compatible para consumidores existentes.
    """

    resultado = (
        resolver_confirmacion_sucursal_via_cargo_ofrecida(
            pedido,
            texto_cliente,
            despacho_completo_fn=despacho_completo_fn,
            es_afirmativo_fn=es_afirmativo_fn,
            log_fn=log_fn,
        )
    )

    return resultado.confirmada
