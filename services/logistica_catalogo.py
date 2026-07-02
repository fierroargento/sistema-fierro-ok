"""
services/logistica_catalogo.py

Adapter entre catálogo de productos y cálculo logístico.

Objetivo:
- Centralizar la búsqueda de productos por SKU.
- Evitar duplicar lógica en reglas puntuales.
- Preparar el camino para SaaS/CRM: catálogo por empresa/tenant/cuenta.
"""

from services.productos_logistica import calcular_logistica_pedido


def buscar_producto_catalogo_por_sku(Producto, sku):
    """Busca un producto del catálogo por SKU normalizado."""
    sku = str(sku or "").strip().upper()
    if not sku:
        return None

    try:
        return Producto.query.filter_by(sku=sku).first()
    except Exception:
        try:
            return Producto.query.filter(Producto.sku.ilike(sku)).first()
        except Exception:
            return None


def calcular_logistica_pedido_desde_catalogo(pedido, Producto=None):
    """Calcula peso/dimensiones/permisos usando el catálogo actual.

    APB/SaaS:
    - Hoy usa app.Producto por compatibilidad con el monolito.
    - La función acepta Producto inyectado para tests y futura separación por tenant.
    - En una fase SaaS, este adapter es el punto donde filtrar por empresa_id/cuenta.
    """
    if Producto is None:
        try:
            from app import Producto as ProductoApp
            Producto = ProductoApp
        except Exception:
            return {
                "ok": False,
                "motivo": "catalogo_no_disponible",
                "permite_correo": False,
                "requiere_revision_logistica": True,
                "faltantes": ["No se pudo acceder al catálogo de productos."],
            }

    return calcular_logistica_pedido(
        pedido,
        buscar_producto_por_sku=lambda sku: buscar_producto_catalogo_por_sku(Producto, sku),
    )
