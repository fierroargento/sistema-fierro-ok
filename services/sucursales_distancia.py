"""
services/sucursales_distancia.py

Servicio común para ordenar sucursales por distancia real al cliente.
No depende de app.py.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Tuple


def float_o_none(valor: Any) -> Optional[float]:
    try:
        if valor in (None, ""):
            return None
        return float(str(valor).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def distancia_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radio_tierra_km = 6371.0

    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )

    return radio_tierra_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _coords_desde_objeto(
    obj: Any,
    campos_lat: Iterable[str],
    campos_lng: Iterable[str],
) -> Tuple[Optional[float], Optional[float]]:
    for campo_lat in campos_lat:
        lat = float_o_none(obj.get(campo_lat)) if isinstance(obj, dict) else float_o_none(getattr(obj, campo_lat, None))

        if lat is None:
            continue

        for campo_lng in campos_lng:
            lng = float_o_none(obj.get(campo_lng)) if isinstance(obj, dict) else float_o_none(getattr(obj, campo_lng, None))

            if lng is not None:
                return lat, lng

    return None, None


def obtener_coordenadas_cliente_pedido(
    pedido: Any,
    *,
    permitir_normalizar: bool = True,
) -> Dict[str, Any]:
    if not pedido:
        return {
            "ok": False,
            "lat": None,
            "lng": None,
            "fuente": "",
            "confianza": "",
            "motivo": "sin_pedido",
        }

    lat, lng = _coords_desde_objeto(
        pedido,
        campos_lat=("latitud_cliente", "lat", "latitude", "latitud"),
        campos_lng=("longitud_cliente", "lng", "lon", "longitude", "longitud"),
    )

    if lat is not None and lng is not None:
        return {
            "ok": True,
            "lat": lat,
            "lng": lng,
            "fuente": str(getattr(pedido, "ubicacion_fuente", "") or "pedido_lat_lng"),
            "confianza": str(getattr(pedido, "ubicacion_confianza", "") or ""),
            "motivo": "",
        }

    if permitir_normalizar:
        try:
            from services.ubicacion_cp import normalizar_ubicacion_pedido

            normalizar_ubicacion_pedido(pedido)
        except Exception as e:
            return {
                "ok": False,
                "lat": None,
                "lng": None,
                "fuente": "",
                "confianza": "",
                "motivo": f"normalizacion_error: {e}",
            }

        lat, lng = _coords_desde_objeto(
            pedido,
            campos_lat=("latitud_cliente", "lat", "latitude", "latitud"),
            campos_lng=("longitud_cliente", "lng", "lon", "longitude", "longitud"),
        )

        if lat is not None and lng is not None:
            return {
                "ok": True,
                "lat": lat,
                "lng": lng,
                "fuente": str(getattr(pedido, "ubicacion_fuente", "") or "ubicacion_cp"),
                "confianza": str(getattr(pedido, "ubicacion_confianza", "") or ""),
                "motivo": "",
            }

    return {
        "ok": False,
        "lat": None,
        "lng": None,
        "fuente": "",
        "confianza": "",
        "motivo": "sin_coordenadas_cliente",
    }


def obtener_coordenadas_sucursal(
    sucursal: Dict[str, Any],
) -> Tuple[Optional[float], Optional[float]]:
    if not isinstance(sucursal, dict):
        return None, None

    lat, lng = _coords_desde_objeto(
        sucursal,
        campos_lat=("lat", "latitud", "latitude"),
        campos_lng=("lng", "lon", "longitud", "longitude"),
    )

    if lat is not None and lng is not None:
        return lat, lng

    location = sucursal.get("location") if isinstance(sucursal.get("location"), dict) else {}
    geo = location.get("geolocation") if isinstance(location.get("geolocation"), dict) else {}

    lat = float_o_none(geo.get("latitude") or geo.get("lat") or geo.get("latitud"))
    lng = float_o_none(geo.get("longitude") or geo.get("lng") or geo.get("lon") or geo.get("longitud"))

    if lat is not None and lng is not None:
        return lat, lng

    raw = sucursal.get("raw") if isinstance(sucursal.get("raw"), dict) else {}
    raw_location = raw.get("location") if isinstance(raw.get("location"), dict) else {}
    raw_geo = raw_location.get("geolocation") if isinstance(raw_location.get("geolocation"), dict) else {}

    lat = float_o_none(raw_geo.get("latitude") or raw_geo.get("lat") or raw_geo.get("latitud"))
    lng = float_o_none(raw_geo.get("longitude") or raw_geo.get("lng") or raw_geo.get("lon") or raw_geo.get("longitud"))

    return lat, lng


def ordenar_sucursales_por_distancia(
    *,
    pedido: Any,
    sucursales: Iterable[Dict[str, Any]],
    radio_max_km: Optional[float] = None,
    limite: Optional[int] = None,
    permitir_normalizar_pedido: bool = True,
) -> Dict[str, Any]:
    coords_cliente = obtener_coordenadas_cliente_pedido(
        pedido,
        permitir_normalizar=permitir_normalizar_pedido,
    )

    if not coords_cliente.get("ok"):
        return {
            "ok": False,
            "sucursales": [],
            "motivo": coords_cliente.get("motivo") or "sin_coordenadas_cliente",
            "cliente": coords_cliente,
        }

    lat_cliente = coords_cliente["lat"]
    lng_cliente = coords_cliente["lng"]

    candidatas: List[Dict[str, Any]] = []

    for sucursal in sucursales or []:
        if not isinstance(sucursal, dict):
            continue

        lat_suc, lng_suc = obtener_coordenadas_sucursal(sucursal)

        if lat_suc is None or lng_suc is None:
            continue

        distancia = distancia_km(
            float(lat_cliente),
            float(lng_cliente),
            float(lat_suc),
            float(lng_suc),
        )

        if radio_max_km is not None and distancia > float(radio_max_km):
            continue

        item = dict(sucursal)
        item["distancia_km"] = round(float(distancia), 2)
        item["distancia_origen"] = coords_cliente.get("fuente") or "cliente_lat_lng"

        candidatas.append(item)

    candidatas.sort(key=lambda s: float(s.get("distancia_km") or 999999))

    if limite:
        candidatas = candidatas[: int(limite)]

    return {
        "ok": bool(candidatas),
        "sucursales": candidatas,
        "motivo": "" if candidatas else "sin_sucursales_con_coordenadas_en_radio",
        "cliente": coords_cliente,
    }
