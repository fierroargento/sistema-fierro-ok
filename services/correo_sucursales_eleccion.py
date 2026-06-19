"""
services/correo_sucursales_eleccion.py
──────────────────────────────────────
Detección segura de la sucursal Correo elegida por el cliente.

Lee únicamente las sucursales que el sistema ya ofreció y guardó en
pedido.correo_sucursales_ofrecidas.
"""

import json
import re
import unicodedata


def _normalizar_texto(valor):
    texto = str(valor or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _cargar_sucursales_ofrecidas(pedido):
    try:
        data = json.loads(getattr(pedido, "correo_sucursales_ofrecidas", "") or "[]")
    except Exception:
        return []

    return data if isinstance(data, list) else []


def _indice_opcion(texto, cantidad):
    texto_norm = _normalizar_texto(texto)

    patrones = [
        (r"(?<!\d)1(?!\d)|primero|primera|la uno|opcion uno|opcion 1", 0),
        (r"(?<!\d)2(?!\d)|segundo|segunda|la dos|opcion dos|opcion 2", 1),
        (r"(?<!\d)3(?!\d)|tercero|tercera|la tres|opcion tres|opcion 3", 2),
        (r"(?<!\d)4(?!\d)|cuarto|cuarta|la cuatro|opcion cuatro|opcion 4", 3),
        (r"(?<!\d)5(?!\d)|quinto|quinta|la cinco|opcion cinco|opcion 5", 4),
    ]

    for patron, indice in patrones:
        if indice < cantidad and re.search(patron, texto_norm):
            return indice

    return None


def _normalizar_sucursal(sucursal):
    return {
        "id": (
            sucursal.get("id")
            or sucursal.get("agencyId")
            or sucursal.get("codigo")
            or sucursal.get("code")
            or ""
        ),
        "nombre": (
            sucursal.get("nombre")
            or sucursal.get("name")
            or sucursal.get("descripcion")
            or sucursal.get("description")
            or "Sucursal Correo"
        ),
        "direccion": (
            sucursal.get("direccion")
            or sucursal.get("address")
            or sucursal.get("domicilio")
            or ""
        ),
        "localidad": (
            sucursal.get("localidad")
            or sucursal.get("city")
            or sucursal.get("ciudad")
            or ""
        ),
        "provincia": (
            sucursal.get("provincia")
            or sucursal.get("province")
            or sucursal.get("state")
            or ""
        ),
        "cp": (
            sucursal.get("cp")
            or sucursal.get("postalCode")
            or sucursal.get("zipCode")
            or ""
        ),
        "raw": sucursal,
    }


def detectar_sucursal_correo_ofrecida(pedido, mensaje):
    sucursales = _cargar_sucursales_ofrecidas(pedido)
    if not sucursales:
        return None

    texto = str(mensaje or "").strip()
    if not texto:
        return None

    indice = _indice_opcion(texto, len(sucursales))
    if indice is not None:
        return _normalizar_sucursal(sucursales[indice])

    texto_norm = _normalizar_texto(texto)

    for sucursal in sucursales:
        normalizada = _normalizar_sucursal(sucursal)
        nombre_norm = _normalizar_texto(normalizada["nombre"])
        direccion_norm = _normalizar_texto(normalizada["direccion"])

        palabras_nombre = [
            p for p in re.split(r"\W+", nombre_norm)
            if len(p) > 3 and p not in {"correo", "sucursal", "agencia", "punto"}
        ]

        if palabras_nombre and all(p in texto_norm for p in palabras_nombre):
            return normalizada

        if direccion_norm and len(direccion_norm) > 5 and direccion_norm in texto_norm:
            return normalizada

    return None
