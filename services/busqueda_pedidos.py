from domain.estados import Estado
from models.pedido import Pedido
from services.telefonos import normalizar_telefono_service


def buscar_pedido_activo_por_telefono_service(
    telefono,
    organizacion_id,
    Pedido,
):
    """Busca el pedido activo más reciente asociado a un teléfono normalizado."""
    tel_norm = normalizar_telefono_service(telefono)

    if not tel_norm:
        return None

    from services.acceso_tenant_pedidos import consulta_pedidos_tenant

    ultimos = (
        consulta_pedidos_tenant(Pedido, organizacion_id)
        .filter(Pedido.estado.notin_([
            Estado.FINALIZADO,
            Estado.CANCELADO,
        ]))
        .order_by(Pedido.id.desc())
        .limit(80)
        .all()
    )

    cola = tel_norm[-8:]

    for pedido in ultimos:
        tel_pedido = normalizar_telefono_service(
            getattr(pedido, "telefono", "")
        )

        if tel_pedido and tel_pedido[-8:] == cola:
            return pedido

    return None


def buscar_pedido_activo_por_telefono(telefono, organizacion_id=None):
    """Busca un pedido activo usando el modelo canónico."""
    if organizacion_id is None:
        return None
    return buscar_pedido_activo_por_telefono_service(
        telefono,
        organizacion_id,
        Pedido,
    )
