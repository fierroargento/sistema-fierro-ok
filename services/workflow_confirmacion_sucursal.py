"""
Confirmación operativa de sucursales ofrecidas.

No hace commit.
No envía mensajes.
No decide canal ni cross-sell.
"""

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


def confirmar_sucursal_via_cargo_ofrecida_sin_persistir(
    pedido,
    texto_cliente,
    *,
    despacho_completo_fn,
    log_fn=print,
):
    """
    Confirma una sucursal Vía Cargo ofrecida al cliente.

    La transacción y las acciones posteriores quedan a cargo
    del llamador.
    """

    if not pedido:
        return False

    if str(
        getattr(pedido, "sucursal_nombre", "")
        or ""
    ).strip():
        return False

    texto_cliente = str(
        texto_cliente or ""
    ).strip()
    if not texto_cliente:
        return False

    try:
        sucursales = cargar_sucursales_via_cargo()
        if not sucursales:
            return False

        decision_sucursal = (
            decidir_sucursal_via_cargo_para_pedido(
                pedido=pedido,
                texto=texto_cliente,
                sucursales_catalogo=sucursales,
                log_error_fn=lambda error: log_fn(
                    "[VIA CARGO] Error usando decision "
                    "central sucursal "
                    f"pedido #{getattr(pedido, 'id', '')}: "
                    f"{error}"
                ),
            )
        )

        if not decision_sucursal.seleccionada:
            return False

        if not aplicar_decision_sucursal_al_pedido(
            pedido,
            decision_sucursal,
            transporte="Vía Cargo",
        ):
            return False

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

        return True

    except Exception as error:
        log_fn(
            "[VIA CARGO] Error confirmando "
            "sucursal ofrecida "
            f"pedido #{getattr(pedido, 'id', '')}: "
            f"{error}"
        )
        return False
