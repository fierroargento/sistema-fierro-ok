"""
modules/transportes/__init__.py
────────────────────────────────
Módulo de transporte.

Estado actual:
- Correo Argentino activo para PP6040.
- Andreani queda en standby hasta credenciales.
"""

from .correo_argentino import cotizar_correo, obtener_sucursales_correo_por_pedido
from .andreani import cotizar_andreani
from .selector import (
    pedido_contiene_pp6040,
    cotizar_correo_pp6040,
    evaluar_decision_correo_pp6040,
    asignar_transporte_pedido,
    sugerir_sucursales_correo_pedido,
)

__all__ = [
    "cotizar_correo",
    "cotizar_andreani",
    "obtener_sucursales_correo_por_pedido",
    "pedido_contiene_pp6040",
    "cotizar_correo_pp6040",
    "evaluar_decision_correo_pp6040",
    "asignar_transporte_pedido",
    "sugerir_sucursales_correo_pedido",
]
