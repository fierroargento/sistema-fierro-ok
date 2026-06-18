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
BANDEJA_TODOS = "todos"

FILTROS_INICIO_VALIDOS = {
    BANDEJA_PENDIENTES_CARGA,
    BANDEJA_PENDIENTES_DESPACHO,
    BANDEJA_SEGUIMIENTO,
    BANDEJA_DEMORA,
    BANDEJA_TODOS,
}

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

def normalizar_filtro_inicio(filtro):
    filtro_normalizado = _texto(filtro)

    if filtro_normalizado not in FILTROS_INICIO_VALIDOS:
        return BANDEJA_TODOS

    return filtro_normalizado


def filtrar_pedidos_por_bandeja(pedidos, filtro, agregado_pendiente_fn=None):
    filtro_normalizado = normalizar_filtro_inicio(filtro)
    pedidos_lista = list(pedidos or [])

    if filtro_normalizado == BANDEJA_TODOS:
        return pedidos_lista

    return [
        pedido for pedido in pedidos_lista
        if clasificar_bandeja_pedido(
            pedido,
            agregado_pendiente_fn=agregado_pendiente_fn,
        ) == filtro_normalizado
    ]


def preparar_bandejas_inicio(pedidos, filtro, agregado_pendiente_fn=None):
    """
    Prepara datos de bandejas para Inicio/Admin.

    APB SaaS:
    app.py no conoce reglas de clasificación ni listas de filtros.
    Solo entrega pedidos + filtro solicitado, y este service devuelve:
    - resumen total sobre la lista visible original;
    - pedidos filtrados;
    - filtro normalizado seguro.
    """
    pedidos_lista = list(pedidos or [])
    filtro_normalizado = normalizar_filtro_inicio(filtro)

    resumen = resumen_operativo_bandejas(
        pedidos_lista,
        agregado_pendiente_fn=agregado_pendiente_fn,
    )

    pedidos_filtrados = filtrar_pedidos_por_bandeja(
        pedidos_lista,
        filtro_normalizado,
        agregado_pendiente_fn=agregado_pendiente_fn,
    )

    return resumen, pedidos_filtrados, filtro_normalizado
