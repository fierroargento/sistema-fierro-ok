"""Formato monetario reutilizable para las vistas administrativas."""

from decimal import Decimal


def formatear_centavos_ars(centavos):
    """Presenta centavos como importe argentino sin alterar el valor."""
    importe = Decimal(int(centavos or 0)) / Decimal(100)
    occidental = f"{importe:,.2f}"
    return occidental.replace(",", "_").replace(".", ",").replace("_", ".")
