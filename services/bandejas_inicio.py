"""
services/bandejas_inicio.py
───────────────────────────
Clasificación de pedidos para bandejas del panel Inicio/Admin.

APB:
Las bandejas no representan canales ni tipos de envío, sino responsabilidad
operativa real:
- Pendientes Carga
- Pendientes Despacho
- Con demora
- En seguimiento
"""

BANDEJA_PENDIENTES_CARGA = "pendientes_carga"
BANDEJA_PENDIENTES_DESPACHO = "pendientes_despacho"
BANDEJA_SEGUIMIENTO = "seguimiento"
BANDEJA_DEMORA = "demora"

ESTADO_CARGANDO = "Cargando Pedido"
ESTADO_ETIQUETA_LISTA = "Etiqueta Lista"
ESTADO_ETIQUETA_IMPRESA = "Etiqueta Impresa"
ESTADO_EMBALADO = "Embalado"
ESTADO_DESPACHADO = "Despachado"
ESTADO_VERIFICAR_DESTINO = "Verificar llegada a destino"
ESTADO_LISTO_RETIRAR = "Listo para retirar"
ESTADO_DEMORA = "Con demora de entrega"
ESTADO_RECLAMO_TRANSPORTE = "Con reclamo en transporte"
ESTADO_NO_ENTREGADO = "No entregado"

ESTADOS_PENDIENTES_DESPACHO = {
    ESTADO_ETIQUETA_LISTA,
    ESTADO_ETIQUETA_IMPRESA,
    ESTADO_EMBALADO,
}

ESTADOS_SEGUIMIENTO = {
    ESTADO_DESPACHADO,
    ESTADO_VERIFICAR_DESTINO,
    ESTADO_LISTO_RETIRAR,
}

ESTADOS_DEMORA = {
    ESTADO_DEMORA,
    ESTADO_RECLAMO_TRANSPORTE,
    ESTADO_NO_ENTREGADO,
}


def _texto(valor):
    return str(valor or "").strip()


def _normalizar(valor):
    return _texto(valor).lower().replace("í", "i")


def estado_pedido(pedido):
    return _texto(getattr(pedido, "estado", ""))


def es_via_cargo_pedido(pedido):
    transporte = _normalizar(getattr(pedido, "empresa_envio", ""))
    return "via cargo" in transporte


def pedido_tiene_seguimiento(pedido):
    return bool(
        _texto(getattr(pedido, "seguimiento", ""))
        or _texto(getattr(pedido, "tn_tracking_number", ""))
    )


def requiere_cargar_seguimiento_via_cargo(pedido):
    """
    Regla operativa:
    Vía Cargo puede despacharse antes de tener seguimiento.
    Ese seguimiento lo carga Carga después del despacho, por eso sigue siendo
    Pendiente Carga aunque el estado ya sea Despachado.
    """
    if not pedido:
        return False

    return bool(
        estado_pedido(pedido) in {
            ESTADO_DESPACHADO,
            ESTADO_RECLAMO_TRANSPORTE,
        }
        and es_via_cargo_pedido(pedido)
        and not pedido_tiene_seguimiento(pedido)
    )


def _tiene_agregado_pendiente(pedido, agregado_pendiente_fn=None):
    if not callable(agregado_pendiente_fn):
        return False

    try:
        return bool(agregado_pendiente_fn(pedido))
    except Exception:
        return False


def pedido_pendiente_carga(pedido, agregado_pendiente_fn=None):
    """
    Pendientes Carga:
    - carga inicial incompleta;
    - cross-sell/agregado pendiente de revisión;
    - Vía Cargo despachado o reclamado sin seguimiento.
    """
    if not pedido:
        return False

    if estado_pedido(pedido) == ESTADO_CARGANDO:
        return True

    if _tiene_agregado_pendiente(pedido, agregado_pendiente_fn):
        return True

    if requiere_cargar_seguimiento_via_cargo(pedido):
        return True

    return False


def pedido_pendiente_despacho(pedido, agregado_pendiente_fn=None):
    """
    Pendientes Despacho:
    pedidos en instancia de impresión, embalaje o despacho.
    Si hay un agregado pendiente, vuelve a Carga y no queda en Despacho.
    """
    if not pedido:
        return False

    if pedido_pendiente_carga(
        pedido,
        agregado_pendiente_fn=agregado_pendiente_fn,
    ):
        return False

    return estado_pedido(pedido) in ESTADOS_PENDIENTES_DESPACHO


def pedido_con_demora(pedido):
    if not pedido:
        return False

    return estado_pedido(pedido) in ESTADOS_DEMORA


def pedido_en_seguimiento(pedido, agregado_pendiente_fn=None):
    """
    En seguimiento:
    post-despacho sin acción pendiente de Carga.
    """
    if not pedido:
        return False

    if pedido_pendiente_carga(
        pedido,
        agregado_pendiente_fn=agregado_pendiente_fn,
    ):
        return False

    if pedido_con_demora(pedido):
        return False

    return estado_pedido(pedido) in ESTADOS_SEGUIMIENTO


def clasificar_bandeja_pedido(pedido, agregado_pendiente_fn=None):
    if pedido_pendiente_carga(
        pedido,
        agregado_pendiente_fn=agregado_pendiente_fn,
    ):
        return BANDEJA_PENDIENTES_CARGA

    if pedido_pendiente_despacho(
        pedido,
        agregado_pendiente_fn=agregado_pendiente_fn,
    ):
        return BANDEJA_PENDIENTES_DESPACHO

    if pedido_con_demora(pedido):
        return BANDEJA_DEMORA

    if pedido_en_seguimiento(
        pedido,
        agregado_pendiente_fn=agregado_pendiente_fn,
    ):
        return BANDEJA_SEGUIMIENTO

    return ""


def resumen_operativo_bandejas(pedidos, agregado_pendiente_fn=None):
    resumen = {
        BANDEJA_PENDIENTES_CARGA: 0,
        BANDEJA_PENDIENTES_DESPACHO: 0,
        BANDEJA_SEGUIMIENTO: 0,
        BANDEJA_DEMORA: 0,
        "total": 0,
    }

    for pedido in pedidos or []:
        bandeja = clasificar_bandeja_pedido(
            pedido,
            agregado_pendiente_fn=agregado_pendiente_fn,
        )

        if bandeja in resumen:
            resumen[bandeja] += 1

        resumen["total"] += 1

    return resumen


def atributos_filtro_pedido(pedido, agregado_pendiente_fn=None):
    return {
        BANDEJA_PENDIENTES_CARGA: "si" if pedido_pendiente_carga(
            pedido,
            agregado_pendiente_fn=agregado_pendiente_fn,
        ) else "no",
        BANDEJA_PENDIENTES_DESPACHO: "si" if pedido_pendiente_despacho(
            pedido,
            agregado_pendiente_fn=agregado_pendiente_fn,
        ) else "no",
        BANDEJA_SEGUIMIENTO: "si" if pedido_en_seguimiento(
            pedido,
            agregado_pendiente_fn=agregado_pendiente_fn,
        ) else "no",
        BANDEJA_DEMORA: "si" if pedido_con_demora(pedido) else "no",
    }
