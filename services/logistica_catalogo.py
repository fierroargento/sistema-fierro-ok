"""
services/logistica_catalogo.py

Adapter entre catálogo de productos y cálculo logístico.

Objetivo:
- Centralizar la búsqueda de productos por SKU.
- Evitar duplicar lógica en reglas puntuales.
- Preparar el camino para SaaS/CRM: catálogo por empresa/tenant/cuenta.
"""

from models.producto import Producto as ProductoModel
from services.productos_logistica import calcular_logistica_pedido


def buscar_producto_catalogo_por_sku(Producto, sku, *, organizacion_id):
    """Busca un producto por SKU únicamente dentro del tenant indicado."""
    sku = str(sku or "").strip().upper()
    if not sku or organizacion_id is None:
        return None

    try:
        return Producto.query.filter_by(
            sku=sku,
            organizacion_id=int(organizacion_id),
        ).first()
    except Exception:
        try:
            return Producto.query.filter(
                Producto.organizacion_id == int(organizacion_id),
                Producto.sku.ilike(sku),
            ).first()
        except Exception:
            return None


def calcular_logistica_pedido_desde_catalogo(pedido, Producto=None):
    """Calcula peso/dimensiones/permisos usando el catálogo actual.

    APB/SaaS:
    - Usa el modelo canónico del catálogo por defecto.
    - Acepta Producto inyectado para tests y futura separación por tenant.
    - En una fase SaaS, este adapter es el punto donde filtrar por empresa_id/cuenta.
    """
    if Producto is None:
        Producto = ProductoModel

    organizacion_id = getattr(pedido, "organizacion_id", None)

    return calcular_logistica_pedido(
        pedido,
        buscar_producto_por_sku=lambda sku: buscar_producto_catalogo_por_sku(
            Producto,
            sku,
            organizacion_id=organizacion_id,
        ),
    )
