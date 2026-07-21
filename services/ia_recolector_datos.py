"""
Primitivas compartidas de datos del recolector IA.

No modifica pedidos.
No importa app.py.
No hace commit ni envía mensajes.
"""

import re
from typing import Any

from services.ia_recolector_sync import (
    ia_cp_valido_recolector,
)
from services.telefonos import (
    normalizar_telefono_service,
)


def capitalizar_texto_fierro(valor: Any) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""

    texto = re.sub(r"\s+", " ", texto)
    minusculas = {
        "de",
        "del",
        "la",
        "las",
        "los",
        "y",
        "e",
    }
    siglas = {"dni", "cp"}

    partes = []
    for palabra in texto.split(" "):
        limpia = palabra.strip()
        if not limpia:
            continue

        base = re.sub(
            r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]",
            "",
            limpia,
        ).lower()

        if base in siglas:
            partes.append(limpia.upper())
        elif base in minusculas:
            partes.append(limpia.lower())
        else:
            partes.append(
                "-".join([
                    (
                        parte[:1].upper()
                        + parte[1:].lower()
                        if parte
                        else parte
                    )
                    for parte in limpia.split("-")
                ])
            )

    return " ".join(partes).strip()


def normalizar_direccion_fierro(valor: Any) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""

    texto = re.sub(r"\s+", " ", texto)
    reemplazos = [
        (r"\bav\.?\b", "Av."),
        (r"\bavenida\b", "Av."),
        (r"\bcalle\b", "Calle"),
        (r"\bnro\.?\b", "N°"),
        (r"\bnº\b", "N°"),
        (r"\bnumero\b", "N°"),
        (r"\bpiso\b", "Piso"),
        (r"\bdpto\.?\b", "Dpto."),
        (r"\bdepartamento\b", "Dpto."),
    ]

    texto = capitalizar_texto_fierro(texto)

    for patron, reemplazo in reemplazos:
        texto = re.sub(
            patron,
            reemplazo,
            texto,
            flags=re.IGNORECASE,
        )

    return texto.strip()


def ia_campo_vacio(valor: Any) -> bool:
    return not str(valor or "").strip()


def ia_dni_valido(valor: Any) -> str:
    limpio = re.sub(
        r"\D+",
        "",
        str(valor or ""),
    )
    return limpio if len(limpio) in (7, 8) else ""


def ia_cp_valido(valor: Any) -> str:
    return ia_cp_valido_recolector(valor)


def ia_texto_menciona_autorizado(texto: Any) -> bool:
    t = str(texto or "").lower()
    patrones = [
        r"\bquien\s+recibe\b",
        r"\bquien\s+retira\b",
        r"\bquien\s+va\s+a\s+recibir\b",
        r"\bquien\s+va\s+a\s+retirar\b",
        r"\bel\s+que\s+recibe\b",
        r"\bla\s+que\s+recibe\b",
        r"\bel\s+que\s+retira\b",
        r"\bla\s+que\s+retira\b",
        r"\brecibe\s+[^,.]{2,80}",
        r"\bretira\s+[^,.]{2,80}",
        r"\bretirar\s+[^,.]{2,80}",
        r"\bautorizad[oa]\b",
        r"\bautorizo\s+a\b",
        r"\bentregar\s+a\b",
        r"\bentrega\s+a\b",
        r"\bse\s+lo\s+entregan\s+a\b",
        r"\ba\s+nombre\s+de\b",
    ]

    return any(
        re.search(patron, t)
        for patron in patrones
    )


def normalizar_datos_ia_fierro(
    datos: Any,
) -> dict[str, Any]:
    if not isinstance(datos, dict):
        return {}

    normalizados = dict(datos)

    for campo in [
        "nombre",
        "apellido",
        "localidad",
        "autorizado_nombre",
    ]:
        if normalizados.get(campo):
            normalizados[campo] = (
                capitalizar_texto_fierro(
                    normalizados.get(campo)
                )
            )

    if normalizados.get("direccion"):
        normalizados["direccion"] = (
            normalizar_direccion_fierro(
                normalizados.get("direccion")
            )
        )

    if normalizados.get("dni"):
        normalizados["dni"] = (
            ia_dni_valido(
                normalizados.get("dni")
            )
            or str(
                normalizados.get("dni") or ""
            ).strip()
        )

    if normalizados.get("autorizado_dni"):
        normalizados["autorizado_dni"] = (
            ia_dni_valido(
                normalizados.get("autorizado_dni")
            )
            or str(
                normalizados.get(
                    "autorizado_dni"
                )
                or ""
            ).strip()
        )

    if normalizados.get("autorizado_telefono"):
        normalizados["autorizado_telefono"] = (
            normalizar_telefono_service(
                normalizados.get(
                    "autorizado_telefono"
                )
            )
        )

    if normalizados.get("codigo_postal"):
        normalizados["codigo_postal"] = str(
            normalizados.get("codigo_postal")
            or ""
        ).strip().upper()

    return normalizados
