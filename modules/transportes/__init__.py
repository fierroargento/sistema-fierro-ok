"""
modules/transportes/__init__.py
────────────────────────────────
Módulo de cotización automática de transportes.
Cotiza Correo Argentino (API MiCorreo) y Andreani (pendiente credenciales).
Elige automáticamente el más conveniente por precio y disponibilidad.

Variables de entorno necesarias:
    CORREO_ARGENTINO_EMAIL=fierro.argentoventas@gmail.com
    CORREO_ARGENTINO_PASSWORD=tu_contraseña
    
    # Cuando tengas credenciales Andreani:
    ANDREANI_USUARIO=...
    ANDREANI_PASSWORD=...
    ANDREANI_CONTRATO=...
"""

from .correo_argentino import cotizar_correo
from .andreani import cotizar_andreani
from .selector import elegir_transporte, cotizar_ambos

__all__ = [
    "cotizar_correo",
    "cotizar_andreani", 
    "cotizar_ambos",
    "elegir_transporte",
]
