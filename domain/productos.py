"""
domain/productos.py

Identificación centralizada de productos para reglas de negocio.

Objetivo:
- Evitar detecciones desparramadas por módulos.
- Evitar reglas por descripción amplia como "PLEGABLE".
- Evitar falsos positivos: PA9060H no debe entrar jamás como PP6040.
- Usar SKU como fuente única para esta regla.
"""


def normalizar_sku(sku):
    """Normaliza SKU para comparación estable."""
    return str(sku or "").strip().upper()


def es_sku_pp6040(sku):
    """
    True si el SKU pertenece a la familia PP6040.

    Regla APB:
    - Se mira SOLO el SKU.
    - Se acepta coincidencia por contenido: PP6040, PP6040H, etc.
    - No se mira descripción ni observaciones.
    - PA9060H no entra porque no contiene PP6040.
    """
    return "PP6040" in normalizar_sku(sku)


def pedido_tiene_pp6040(pedido):
    """True si algún item del pedido tiene PP6040 en el SKU."""
    if not pedido:
        return False

    for item in (getattr(pedido, "items", None) or []):
        if es_sku_pp6040(getattr(item, "sku", "")):
            return True

    return False
