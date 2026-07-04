"""
services/sucursal_consulta_mixta.py

Reglas para mensajes mixtos sobre sucursales.

Caso esperado:
- el cliente confirma una sucursal ofrecida,
- y además hace una consulta secundaria, por ejemplo horarios.

La consulta secundaria no debe bloquear la elección de sucursal.
"""

import re
import unicodedata


MARCA_HORARIOS_RETIRO = "Cliente consultó horarios de retiro/atención de la sucursal"


def _normalizar(texto):
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9ñ\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def cliente_consulta_horarios_retiro(texto):
    texto_norm = _normalizar(texto)

    if not texto_norm:
        return False

    palabras_horario = [
        "horario",
        "horarios",
        "hora",
        "horas",
        "atienden",
        "atencion",
        "abren",
        "cierra",
        "cierran",
    ]

    contexto_retiro = [
        "retirar",
        "retiro",
        "buscar",
        "busco",
        "sucursal",
        "correo",
        "local",
        "entrega",
    ]

    return (
        any(palabra in texto_norm for palabra in palabras_horario)
        and any(palabra in texto_norm for palabra in contexto_retiro)
    )


def agregar_respuesta_neutra_horarios_retiro(texto_base, texto_cliente):
    if not cliente_consulta_horarios_retiro(texto_cliente):
        return texto_base

    extra = (
        "Sobre los horarios de retiro/atención, no tenemos la información exacta "
        "desde acá. Lo dejamos anotado para que un operador te ayude con esa duda."
    )

    return f"{str(texto_base or '').rstrip()}\n\n{extra}"


def marcar_consulta_horarios_retiro_pendiente(pedido, texto_cliente):
    if not pedido:
        return False

    if not cliente_consulta_horarios_retiro(texto_cliente):
        return False

    resumen = str(getattr(pedido, "ia_resumen", "") or "").strip()

    if MARCA_HORARIOS_RETIRO not in resumen:
        pedido.ia_resumen = f"{resumen} | {MARCA_HORARIOS_RETIRO}".strip(" |")[:1000]

    if hasattr(pedido, "ml_mensajes_pendientes"):
        pedido.ml_mensajes_pendientes = True

    if hasattr(pedido, "ml_mensajes_pendientes_count"):
        pedido.ml_mensajes_pendientes_count = max(
            int(getattr(pedido, "ml_mensajes_pendientes_count", 0) or 0),
            1,
        )

    if hasattr(pedido, "ia_requiere_operador"):
        pedido.ia_requiere_operador = True

    return True
