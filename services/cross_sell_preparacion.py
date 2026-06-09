"""
services/cross_sell_preparacion.py
────────────────────────────────
Reglas operativas para cross-sell cuando el pedido ya está en preparación.

APB / SaaS:
- No cambiar estados hacia atrás.
- No mezclar lógica de negocio en app.py.
- Centralizar la regla para que WhatsApp, Inicio, Despacho y futuras APIs
  consulten el mismo criterio.
"""

from datetime import datetime

from domain.estados import Estado


ESTADOS_PREPARACION_CROSS_SELL = {
    Estado.ETIQUETA_LISTA,
    Estado.ETIQUETA_IMPRESA,
    Estado.EMBALADO,
}


RESULTADOS_RESOLUCION_AGREGADO = {
    "agregado_confirmado",
    "sin_agregado",
    "sin_respuesta",
    "excepcion_operador",
}


def pedido_en_preparacion_cross_sell(pedido):
    """
    Devuelve True si el pedido está en una etapa donde una respuesta
    de cross-sell todavía puede frenar preparación/despacho.

    Etiqueta Lista = acción Imprimir etiqueta.
    Etiqueta Impresa = acción Embalar pedido.
    Embalado = acción Despachar pedido.
    """
    if not pedido:
        return False

    return getattr(pedido, "estado", None) in ESTADOS_PREPARACION_CROSS_SELL


def tiene_agregado_pendiente_en_preparacion(pedido):
    """
    Devuelve True si el pedido está en preparación y tiene un agregado
    pendiente que debe resolver Carga antes de que Despacho continúe.
    """
    if not pedido:
        return False

    return bool(
        getattr(pedido, "agregado_pendiente_revision", False)
        and pedido_en_preparacion_cross_sell(pedido)
    )


def debe_mostrar_en_inicio_carga_por_agregado(pedido):
    """
    Carga debe volver a ver en Inicio los pedidos que siguen en preparación
    pero tienen agregado/cross-sell pendiente.
    """
    return tiene_agregado_pendiente_en_preparacion(pedido)


def debe_bloquear_avance_por_agregado(pedido):
    """
    Si hay agregado pendiente en preparación, se bloquea el próximo avance:
    - Etiqueta Lista -> Etiqueta Impresa
    - Etiqueta Impresa -> Embalado
    - Embalado -> Despachado
    """
    return tiene_agregado_pendiente_en_preparacion(pedido)


def mensaje_bloqueo_agregado_pendiente():
    return (
        "AGREGADO PENDIENTE: el cliente mostró interés en un cross-sell. "
        "Carga debe gestionar el agregado antes de continuar con impresión, "
        "embalado o despacho."
    )


def marcar_interes_cross_sell_preparacion(
    pedido,
    db,
    registrar_evento,
    sku="",
    cantidad=1,
    texto_cliente="",
    origen="cliente",
    canal="wa",
    owner="bot",
):
    """
    Marca un pedido en preparación como bloqueado por interés de cross-sell.

    No cambia el estado del pedido.
    No borra etiqueta.
    No borra seguimiento.
    No toca logística.
    """
    if not pedido_en_preparacion_cross_sell(pedido):
        return False

    pedido.agregado_pendiente_revision = True
    pedido.agregado_revision_fecha = None
    pedido.agregado_revision_usuario = None

    if registrar_evento:
        registrar_evento(
            pedido=pedido,
            tipo_evento="cross_sell_cliente_interesado_preparacion",
            origen=origen,
            canal=canal,
            owner=owner,
            estado_conversacional="cross_sell",
            payload={
                "sku": sku,
                "cantidad": cantidad,
                "estado_pedido": getattr(pedido, "estado", ""),
                "texto_cliente": texto_cliente,
            },
            resultado="ok",
            detalle=(
                "Cliente mostró interés en cross-sell con pedido en preparación. "
                "Se marca agregado pendiente para frenar preparación/despacho "
                "y devolverlo a Carga."
            ),
            procesado=True,
        )

    db.session.commit()
    return True


def resolver_agregado_pendiente(
    pedido,
    db,
    usuario="",
    resultado="",
    observacion="",
    registrar_evento=None,
    registrar_auditoria=None,
):
    """
    Cierra el bloqueo de agregado pendiente y habilita a Despacho a continuar.

    resultado permitido:
    - agregado_confirmado
    - sin_agregado
    - sin_respuesta
    - excepcion_operador
    """
    if not pedido:
        return False, "No se encontró el pedido."

    resultado = str(resultado or "").strip()

    if resultado not in RESULTADOS_RESOLUCION_AGREGADO:
        return False, "Resultado de resolución inválido."

    if not getattr(pedido, "agregado_pendiente_revision", False):
        return False, "El pedido no tiene agregado pendiente."

    pedido.agregado_pendiente_revision = False
    pedido.agregado_revision_fecha = datetime.utcnow()
    pedido.agregado_revision_usuario = usuario or ""

    tipo_evento_por_resultado = {
        "agregado_confirmado": "cross_sell_agregado_confirmado",
        "sin_agregado": "cross_sell_cerrado_sin_agregado",
        "sin_respuesta": "cross_sell_descartado_sin_respuesta",
        "excepcion_operador": "cross_sell_excepcion_operador",
    }

    detalle = (
        f"Agregado pendiente resuelto por Carga. "
        f"Resultado: {resultado}."
    )

    if observacion:
        detalle += f" Observación: {observacion}"

    if registrar_evento:
        registrar_evento(
            pedido=pedido,
            tipo_evento=tipo_evento_por_resultado[resultado],
            origen="operador",
            canal="sistema",
            owner="operador",
            estado_conversacional="cross_sell",
            payload={
                "resultado": resultado,
                "observacion": observacion,
                "estado_pedido": getattr(pedido, "estado", ""),
            },
            resultado="ok",
            detalle=detalle,
            usuario=usuario,
            procesado=True,
        )

    if registrar_auditoria:
        registrar_auditoria(
            "Resolvió agregado pendiente por cross-sell",
            entidad="pedido",
            entidad_id=getattr(pedido, "id", None),
            detalle=detalle,
        )

    db.session.commit()
    return True, "Agregado pendiente resuelto. Despacho puede continuar."