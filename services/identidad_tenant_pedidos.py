"""Diagnóstico offline de identidad tenant para pedidos existentes."""


def _entero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def construir_indices_vinculos(vinculos):
    por_ml, por_tn = {}, {}
    for vinculo in vinculos or []:
        identidad = (
            _entero(getattr(vinculo, "organizacion_id", None)),
            _entero(getattr(vinculo, "unidad_negocio_id", None)),
        )
        ml_id = _entero(getattr(vinculo, "mercado_libre_cuenta_id", None))
        tn_id = _entero(getattr(vinculo, "tienda_nube_cuenta_id", None))
        if ml_id is not None:
            por_ml.setdefault(ml_id, set()).add(identidad)
        if tn_id is not None:
            por_tn.setdefault(tn_id, set()).add(identidad)
    return por_ml, por_tn


def candidatos_pedido(pedido, indices):
    por_ml, por_tn = indices
    candidatos = set()
    ml_id = _entero(getattr(pedido, "ml_cuenta_id", None))
    tn_id = _entero(getattr(pedido, "tn_cuenta_id", None))
    if ml_id is not None:
        candidatos.update(por_ml.get(ml_id, set()))
    if tn_id is not None:
        candidatos.update(por_tn.get(tn_id, set()))
    return candidatos


def diagnosticar_identidad_tenant_pedidos(pedidos, vinculos):
    """Clasifica sin escribir; una cuenta vinculada actúa solo como candidato."""
    indices = construir_indices_vinculos(vinculos)

    conteos = {
        "asignados": 0,
        "inferibles": 0,
        "pendientes": 0,
        "ambiguos": 0,
        "conflictos": 0,
    }
    detalle = []
    for pedido in pedidos or []:
        candidatos = candidatos_pedido(pedido, indices)

        explicita = (
            _entero(getattr(pedido, "organizacion_id", None)),
            _entero(getattr(pedido, "unidad_negocio_id", None)),
        )
        tiene_explicita = explicita[0] is not None
        if tiene_explicita and candidatos and explicita not in candidatos:
            estado = "conflicto"
        elif tiene_explicita:
            estado = "asignado"
        elif len(candidatos) == 1:
            estado = "inferible"
        elif len(candidatos) > 1:
            estado = "ambiguo"
        else:
            estado = "pendiente"

        clave_conteo = {
            "asignado": "asignados",
            "inferible": "inferibles",
            "pendiente": "pendientes",
            "ambiguo": "ambiguos",
            "conflicto": "conflictos",
        }[estado]
        conteos[clave_conteo] += 1
        if estado != "asignado" and len(detalle) < 100:
            detalle.append({
                "pedido_id": getattr(pedido, "id", None),
                "estado": estado,
                "candidatos": sorted(candidatos),
            })

    bloqueos = []
    if conteos["pendientes"]:
        bloqueos.append("Hay pedidos sin una cuenta vinculada que permita atribuirlos.")
    if conteos["ambiguos"]:
        bloqueos.append("Hay pedidos con más de un tenant candidato.")
    if conteos["conflictos"]:
        bloqueos.append("Hay pedidos cuya identidad asignada contradice su cuenta.")
    if conteos["inferibles"]:
        bloqueos.append("Los candidatos todavía requieren aprobación antes de persistirse.")

    return {
        **conteos,
        "total": sum(conteos.values()),
        "detalle": detalle,
        "detalle_limitado": True,
        "aprobada": not bloqueos,
        "bloqueos": bloqueos,
        "escrituras_realizadas": 0,
        "integraciones_habilitables": False,
    }


def obtener_diagnostico_identidad_tenant_pedidos(
    *, Pedido, VinculoCanalComercial,
):
    return diagnosticar_identidad_tenant_pedidos(
        Pedido.query.order_by(Pedido.id.asc()).yield_per(500),
        VinculoCanalComercial.query.order_by(
            VinculoCanalComercial.id.asc()
        ).all(),
    )
