"""
services/ubicacion_cp.py

Resolución interna de ubicación por código postal.

Objetivo SaaS/CRM:
- Mantener la lógica fuera de app.py.
- Permitir que mañana la fuente sea una tabla por empresa, una API,
  un JSON completo de CP argentinos o una configuración por cliente.
- No inventar datos si el CP no se puede resolver con seguridad.
"""

import json
import os


def _normalizar_cp(cp):
    cp = str(cp or "").strip()
    cp = "".join(ch for ch in cp if ch.isdigit())
    return cp if len(cp) == 4 else ""


def _normalizar_texto(valor):
    return str(valor or "").strip()


def _cargar_json_seguro(path):
    try:
        if not os.path.exists(path):
            return None

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data

    except Exception:
        return None


def _resolver_desde_codigos_postales_ar(cp):
    """
    Fuente futura recomendada:
    data/codigos_postales_ar.json

    Formatos aceptados:
    [
      {"cp": "3514", "localidad": "Makallé", "provincia": "Chaco"},
      {"codigo_postal": "3514", "localidad": "Makallé", "provincia": "Chaco"}
    ]

    Solo devuelve resultado si hay una única coincidencia clara.
    """
    data = _cargar_json_seguro(os.path.join("data", "codigos_postales_ar.json"))

    if not isinstance(data, list):
        return None

    coincidencias = []

    for item in data:
        if not isinstance(item, dict):
            continue

        item_cp = _normalizar_cp(
            item.get("cp")
            or item.get("codigo_postal")
            or item.get("codigoPostal")
            or item.get("postal_code")
        )

        if item_cp != cp:
            continue

        localidad = _normalizar_texto(
            item.get("localidad")
            or item.get("locality")
            or item.get("ciudad")
            or item.get("city")
        )

        provincia = _normalizar_texto(
            item.get("provincia")
            or item.get("province")
            or item.get("state")
        )

        if localidad or provincia:
            coincidencias.append({
                "codigo_postal": cp,
                "localidad": localidad,
                "provincia": provincia,
                "fuente": "codigos_postales_ar",
            })

    coincidencias_unicas = []
    vistos = set()

    for item in coincidencias:
        clave = (
            item.get("localidad", "").lower(),
            item.get("provincia", "").lower(),
        )

        if clave in vistos:
            continue

        vistos.add(clave)
        coincidencias_unicas.append(item)

    if len(coincidencias_unicas) == 1:
        return coincidencias_unicas[0]

    return None


def _resolver_desde_via_cargo_sucursales(cp):
    """
    Fallback temporal:
    usa via_cargo_sucursales.json si existe.

    APB:
    Esta fuente representa sucursales, no una base completa de CP argentinos.
    Solo se usa si el CP tiene una única localidad/provincia asociada.
    Si hay varias, no inventa.
    """
    data = _cargar_json_seguro("via_cargo_sucursales.json")

    if not isinstance(data, list):
        return None

    coincidencias = []

    for item in data:
        if not isinstance(item, dict):
            continue

        item_cp = _normalizar_cp(
            item.get("cp")
            or item.get("codigo_postal")
            or item.get("codigoPostal")
            or item.get("postal_code")
        )

        if item_cp != cp:
            continue

        localidad = _normalizar_texto(
            item.get("localidad")
            or item.get("locality")
            or item.get("ciudad")
            or item.get("city")
        )

        provincia = _normalizar_texto(
            item.get("provincia")
            or item.get("province")
            or item.get("state")
        )

        if localidad or provincia:
            coincidencias.append({
                "codigo_postal": cp,
                "localidad": localidad,
                "provincia": provincia,
                "fuente": "via_cargo_sucursales",
            })

    coincidencias_unicas = []
    vistos = set()

    for item in coincidencias:
        clave = (
            item.get("localidad", "").lower(),
            item.get("provincia", "").lower(),
        )

        if clave in vistos:
            continue

        vistos.add(clave)
        coincidencias_unicas.append(item)

    if len(coincidencias_unicas) == 1:
        return coincidencias_unicas[0]

    return None


def resolver_ubicacion_por_cp(cp):
    """
    Resuelve localidad/provincia por código postal.

    Retorna:
    {
        "codigo_postal": "3514",
        "localidad": "...",
        "provincia": "...",
        "fuente": "..."
    }

    o None si no puede resolver de forma segura.
    """
    cp = _normalizar_cp(cp)

    if not cp:
        return None

    # Fuente prioritaria SaaS/futura.
    resultado = _resolver_desde_codigos_postales_ar(cp)
    if resultado:
        return resultado

    # Fallback temporal con lo que ya tiene el sistema.
    resultado = _resolver_desde_via_cargo_sucursales(cp)
    if resultado:
        return resultado

    return None


def autocompletar_pedido_por_cp(pedido):
    """
    Completa localidad/provincia del pedido usando codigo_postal.

    No pisa datos existentes.
    No inventa si el CP no se puede resolver.
    Devuelve lista de campos completados.
    """
    if not pedido:
        return []

    cp = _normalizar_cp(getattr(pedido, "codigo_postal", ""))

    if not cp:
        return []

    ubicacion = resolver_ubicacion_por_cp(cp)

    if not ubicacion:
        return []

    completados = []

    localidad_actual = _normalizar_texto(getattr(pedido, "localidad", ""))
    provincia_actual = _normalizar_texto(getattr(pedido, "provincia", ""))

    localidad = _normalizar_texto(ubicacion.get("localidad"))
    provincia = _normalizar_texto(ubicacion.get("provincia"))

    if localidad and not localidad_actual:
        pedido.localidad = localidad[:100]
        completados.append("localidad")

    if provincia and not provincia_actual:
        pedido.provincia = provincia[:100]
        completados.append("provincia")

    return completados