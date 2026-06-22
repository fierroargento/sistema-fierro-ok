"""
services/via_cargo_sucursales.py

Selector modular de sucursales Vía Cargo.

Objetivo:
- Sacar de app.py la lógica de filtrado/ordenamiento de sucursales.
- Reutilizar services.sucursales_distancia.
- Mantener reglas compatibles con el flujo actual:
  1) CP exacto
  2) localidad + provincia
  3) provincia como universo amplio
  4) distancia real como criterio final
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional


VIA_CARGO_SUCURSALES_PATH = "via_cargo_sucursales.json"


def _norm(valor: Any) -> str:
    texto = str(valor or "").lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\s*\(.*?\)", "", texto).strip()
    texto = " ".join(texto.split())
    return texto


def _cp(valor: Any) -> str:
    return "".join(ch for ch in str(valor or "") if ch.isdigit())


def _es_caba(localidad: str, provincia: str) -> bool:
    loc = _norm(localidad)
    prov = _norm(provincia)

    return bool(
        loc in {
            "caba",
            "capital federal",
            "ciudad autonoma de buenos aires",
        }
        or any(
            x in prov
            for x in [
                "capital federal",
                "caba",
                "ciudad autonoma",
                "ciudad autonoma de buenos aires",
            ]
        )
    )


def cargar_sucursales_via_cargo(path: str = VIA_CARGO_SUCURSALES_PATH) -> List[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as archivo:
            data = json.load(archivo)
    except Exception as e:
        print(f"[VIA CARGO] No se pudo leer {path}: {e}")
        return []

    return data if isinstance(data, list) else []


def filtrar_candidatas_via_cargo(
    pedido: Any,
    sucursales: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Filtra el universo de candidatas con las reglas históricas de Vía Cargo.

    La distancia NO se decide acá. Este filtro solo reduce el universo:
    - CABA: sucursales de Capital Federal.
    - Interior: CP exacto, luego localidad + provincia, luego provincia.
    """
    if not pedido:
        return []

    loc = _norm(getattr(pedido, "localidad", "") or "")
    prov = _norm(getattr(pedido, "provincia", "") or "")
    cp = _cp(getattr(pedido, "codigo_postal", "") or "")

    if not cp or len(cp) < 4:
        return []

    data = [s for s in sucursales or [] if isinstance(s, dict)]

    if _es_caba(loc, prov):
        return [
            s for s in data
            if "capital federal" in _norm(s.get("provincia"))
            or "caba" in _norm(s.get("provincia"))
        ]

    candidatas = [
        s for s in data
        if cp and _cp(s.get("cp") or s.get("codigo_postal")) == cp
    ]

    if candidatas:
        return candidatas

    if loc:
        candidatas = [
            s for s in data
            if loc in _norm(s.get("localidad"))
            and (not prov or prov in _norm(s.get("provincia")))
        ]

    if candidatas:
        return candidatas

    if prov:
        candidatas = [
            s for s in data
            if prov in _norm(s.get("provincia"))
        ]

    return candidatas


def seleccionar_sucursales_via_cargo_pedido(
    pedido: Any,
    *,
    sucursales: Optional[Iterable[Dict[str, Any]]] = None,
    limite: int = 3,
    radio_max_km: Optional[float] = None,
    exigir_distancia: bool = True,
    permitir_normalizar_pedido: bool = True,
) -> List[Dict[str, Any]]:
    """Devuelve sucursales Vía Cargo ordenadas por distancia real.

    APB:
    - Por defecto exige poder calcular distancia.
    - Si exigir_distancia=False, permite compatibilidad hacia atrás:
      si no puede ordenar por distancia, devuelve las primeras candidatas.
    """
    if sucursales is None:
        sucursales = cargar_sucursales_via_cargo()

    candidatas = filtrar_candidatas_via_cargo(pedido, sucursales)

    if not candidatas:
        return []

    if radio_max_km is None:
        raw_radio = str(os.getenv("VIA_CARGO_SUCURSALES_RADIO_MAX_KM", "") or "").strip()
        if raw_radio:
            try:
                radio_max_km = float(raw_radio.replace(",", "."))
            except ValueError:
                radio_max_km = None

    from services.sucursales_distancia import ordenar_sucursales_por_distancia

    resultado = ordenar_sucursales_por_distancia(
        pedido=pedido,
        sucursales=candidatas,
        radio_max_km=radio_max_km,
        limite=limite,
        permitir_normalizar_pedido=permitir_normalizar_pedido,
    )

    if resultado.get("ok"):
        return resultado.get("sucursales") or []

    if exigir_distancia:
        return []

    return candidatas[: int(limite)]


def armar_sugerencia_via_cargo_pedido(
    pedido: Any,
    *,
    sucursales: Optional[Iterable[Dict[str, Any]]] = None,
    limite: int = 3,
    radio_max_km: Optional[float] = None,
    exigir_distancia: bool = True,
) -> Dict[str, Any]:
    """Arma respuesta completa para que app.py solo tenga que delegar."""
    seleccionadas = seleccionar_sucursales_via_cargo_pedido(
        pedido,
        sucursales=sucursales,
        limite=limite,
        radio_max_km=radio_max_km,
        exigir_distancia=exigir_distancia,
    )

    if not seleccionadas:
        return {
            "ok": False,
            "sucursales": [],
            "ids_ofrecidas": [],
            "mensaje": "",
            "motivo": "sin_sucursales_via_cargo_confiables",
        }

    from services.mensajes_sucursales import armar_mensaje_sucursales

    ids_ofrecidas = [
        s.get("id")
        for s in seleccionadas
        if s.get("id")
    ]

    return {
        "ok": True,
        "sucursales": seleccionadas,
        "ids_ofrecidas": ids_ofrecidas,
        "mensaje": armar_mensaje_sucursales(seleccionadas, transporte="Vía Cargo"),
        "motivo": "",
    }
