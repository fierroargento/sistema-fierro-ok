"""
services/whatsapp_template_params.py
────────────────────────────────────
Sanitización APB de parámetros para templates Meta WhatsApp.

Meta rechaza parámetros de template con:
- saltos de línea
- tabs
- más de 4 espacios consecutivos

Este service centraliza la limpieza para no repetir reglas en cada flujo.
"""

import re


def sanitizar_parametro_template_meta(valor):
    texto = str(valor or "")

    texto = texto.replace("\r", " ")
    texto = texto.replace("\n", " ")
    texto = texto.replace("\t", " ")

    texto = re.sub(r"\s{2,}", " ", texto)

    return texto.strip()


def sanitizar_parametros_template_meta(parametros):
    return [
        sanitizar_parametro_template_meta(valor)
        for valor in (parametros or [])
    ]
