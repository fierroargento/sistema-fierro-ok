"""
services/correo_detalle_operativo.py

Arma una vista operativa de Correo Argentino para el operador.

No consulta APIs.
No crea envíos.
No paga etiquetas.
Solo normaliza lo que ya está guardado en el pedido:
- costos
- sucursales ofrecidas
- sucursal elegida
- umbrales operativos
- resumen de decisión
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Dict, List, Optional


def _texto(valor: Any) -> str:
    return str(valor or "").strip()


def _norm(valor: Any) -> str:
    texto = _texto(valor).lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _float_o_none(valor: Any) -> Optional[float]:
    try:
        if valor in (None, ""):
            return None
        return float(str(valor).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def _moneda(valor: Any) -> str:
    numero = _float_o_none(valor)
    if numero is None:
        return ""
    return f"${numero:,.0f}".replace(",", ".")


def _json_lista(valor: Any) -> List[Dict[str, Any]]:
    try:
        data = json.loads(valor or "[]")
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    return [item for item in data if isinstance(item, dict)]


def _valor_sucursal(sucursal: Dict[str, Any], *claves: str) -> str:
    for clave in claves:
        valor = sucursal.get(clave)
        if valor not in (None, ""):
            return _texto(valor)
    return ""


def normalizar_sucursal_correo_detalle(sucursal: Dict[str, Any]) -> Dict[str, Any]:
    raw = sucursal.get("raw") if isinstance(sucursal.get("raw"), dict) else {}

    nombre = _valor_sucursal(
        sucursal,
        "nombre",
        "name",
        "descripcion",
        "agency_name",
    ) or _valor_sucursal(
        raw,
        "nombre",
        "name",
        "descripcion",
        "agency_name",
    )

    direccion = _valor_sucursal(
        sucursal,
        "direccion",
        "address",
        "domicilio",
    ) or _valor_sucursal(
        raw,
        "direccion",
        "address",
        "domicilio",
    )

    localidad = _valor_sucursal(
        sucursal,
        "localidad",
        "city",
        "ciudad",
    ) or _valor_sucursal(
        raw,
        "localidad",
        "city",
        "ciudad",
    )

    provincia = _valor_sucursal(
        sucursal,
        "provincia",
        "province",
        "state",
    ) or _valor_sucursal(
        raw,
        "provincia",
        "province",
        "state",
    )

    cp = _valor_sucursal(
        sucursal,
        "cp",
        "postalCode",
        "zipCode",
        "codigo_postal",
    ) or _valor_sucursal(
        raw,
        "cp",
        "postalCode",
        "zipCode",
        "codigo_postal",
    )

    return {
        "id": _valor_sucursal(sucursal, "id", "agencyId", "agency_id", "codigo")
        or _valor_sucursal(raw, "id", "agencyId", "agency_id", "codigo"),
        "nombre": nombre,
        "direccion": direccion,
        "localidad": localidad,
        "provincia": provincia,
        "cp": cp,
        "distancia_km": _float_o_none(sucursal.get("distancia_km")),
        "raw": sucursal,
    }


def _sucursal_elegida_desde_pedido(pedido: Any, sucursales: List[Dict[str, Any]]) -> Dict[str, Any]:
    nombre_pedido = _texto(getattr(pedido, "sucursal_nombre", ""))
    if nombre_pedido:
        nombre_norm = _norm(nombre_pedido)
        for sucursal in sucursales:
            if nombre_norm and nombre_norm == _norm(sucursal.get("nombre")):
                return sucursal

    return {
        "id": "",
        "nombre": nombre_pedido,
        "direccion": _texto(getattr(pedido, "direccion", "")),
        "localidad": _texto(getattr(pedido, "localidad", "")),
        "provincia": _texto(getattr(pedido, "provincia", "")),
        "cp": _texto(getattr(pedido, "codigo_postal", "")),
        "distancia_km": None,
        "raw": {},
    }


def detalle_operativo_correo_pedido(pedido: Any, preferencias: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    empresa = _texto(getattr(pedido, "empresa_envio", ""))
    es_correo = "correo" in _norm(empresa)

    if preferencias is None:
        try:
            from services.correo_argentino_operacion import obtener_preferencias_operativas_correo
            preferencias = obtener_preferencias_operativas_correo()
        except Exception:
            preferencias = {}

    sucursales = [
        normalizar_sucursal_correo_detalle(s)
        for s in _json_lista(getattr(pedido, "correo_sucursales_ofrecidas", ""))
    ]

    costo_envio = _float_o_none(getattr(pedido, "costo_envio", None))
    costo_sucursal = _float_o_none(getattr(pedido, "costo_envio_sucursal", None))
    costo_domicilio = _float_o_none(getattr(pedido, "costo_envio_domicilio", None))

    sucursal_elegida = _sucursal_elegida_desde_pedido(pedido, sucursales)

    tiene_datos_correo = bool(
        es_correo
        or sucursales
        or costo_sucursal is not None
        or costo_domicilio is not None
        or (
            costo_envio is not None
            and "correo" in _norm(getattr(pedido, "ia_resumen", ""))
        )
    )

    if not tiene_datos_correo:
        sucursal_elegida = {
            "id": "",
            "nombre": "",
            "direccion": "",
            "localidad": "",
            "provincia": "",
            "cp": "",
            "distancia_km": None,
            "raw": {},
        }

    return {
        "es_correo": es_correo,
        "empresa_envio": empresa,
        "tipo_entrega": _texto(getattr(pedido, "tipo_entrega", "")),
        "costo_envio": costo_envio,
        "costo_envio_texto": _moneda(costo_envio),
        "costo_sucursal": costo_sucursal,
        "costo_sucursal_texto": _moneda(costo_sucursal),
        "costo_domicilio": costo_domicilio,
        "costo_domicilio_texto": _moneda(costo_domicilio),
        "umbral_acordas": _float_o_none(preferencias.get("max_costo_correo_sucursal_acordas")),
        "umbral_acordas_texto": _moneda(preferencias.get("max_costo_correo_sucursal_acordas")),
        "umbral_pp6040": _float_o_none(preferencias.get("max_costo_correo_sucursal_pp6040")),
        "umbral_pp6040_texto": _moneda(preferencias.get("max_costo_correo_sucursal_pp6040")),
        "requiere_operador_para_pago_etiqueta": bool(
            preferencias.get("requiere_operador_para_pago_etiqueta")
        ),
        "priorizar_correo_sucursal_acordas": bool(
            preferencias.get("priorizar_correo_sucursal_acordas")
        ),
        "sucursales_ofrecidas": sucursales,
        "sucursal_elegida": sucursal_elegida,
        "ia_resumen": _texto(getattr(pedido, "ia_resumen", "")),
        "tiene_datos": tiene_datos_correo,
    }
