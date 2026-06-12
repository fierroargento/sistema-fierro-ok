"""
services/pedidos_acciones.py

Reglas puras para decidir acciones operativas de pedidos.

APB modular:
- Este módulo no usa Flask.
- No arma URLs.
- No renderiza botones.
- Solo decide reglas de negocio.
"""


def debe_mostrar_accion_completar_carga(
    pedido,
    necesita_completar_carga_tn=False,
    requiere_contacto=False,
    estados_post_despacho=None,
    estados_despacho_operativo=None,
):
    """
    Decide si la acción principal debe ser "Completar carga".

    Reglas actuales migradas desde app.py:
    - Tienda Nube con carga incompleta debe volver a completar carga.
    - Si falta contacto/datos operativos y el pedido no está en estados posteriores,
      también debe completar carga.
    """
    if not pedido:
        return False

    if necesita_completar_carga_tn:
        return True

    estados_post_despacho = estados_post_despacho or []
    estados_despacho_operativo = estados_despacho_operativo or []

    estados_excluidos = list(estados_post_despacho) + list(estados_despacho_operativo) + [
        "Entregado",
        "Finalizado",
    ]

    return bool(
        requiere_contacto
        and getattr(pedido, "estado", None) not in estados_excluidos
    )
