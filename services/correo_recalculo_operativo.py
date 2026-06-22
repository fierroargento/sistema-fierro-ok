"""
services/correo_recalculo_operativo.py

Recalcula datos operativos de Correo Argentino para un pedido.

No envía mensajes al cliente.
No paga etiquetas.
No genera envíos en MiCorreo.

Solo actualiza datos guardados para el operador:
- correo_sucursales_ofrecidas
- empresa_envio / tipo_entrega
- sucursal_nombre si corresponde limpiarla
- ia_resumen con trazabilidad
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional


def _texto(valor: Any) -> str:
    return str(valor or "").strip()


def _norm(valor: Any) -> str:
    texto = _texto(valor).lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _id_sucursal(sucursal: Dict[str, Any]) -> str:
    return _texto(
        sucursal.get("id")
        or sucursal.get("agencyId")
        or sucursal.get("agency_id")
        or sucursal.get("codigo")
    )


def _nombre_sucursal(sucursal: Dict[str, Any]) -> str:
    return _texto(
        sucursal.get("nombre")
        or sucursal.get("name")
        or sucursal.get("descripcion")
        or sucursal.get("agency_name")
    )


def _coincide_sucursal(nombre_actual: str, sucursal: Dict[str, Any]) -> bool:
    actual = _norm(nombre_actual)
    if not actual:
        return False

    nombre = _norm(_nombre_sucursal(sucursal))
    if actual and nombre and (actual == nombre or actual in nombre or nombre in actual):
        return True

    return False


def _agregar_resumen(pedido: Any, marca: str) -> None:
    if not hasattr(pedido, "ia_resumen"):
        return

    resumen = _texto(getattr(pedido, "ia_resumen", ""))
    if marca not in resumen:
        pedido.ia_resumen = f"{resumen} | {marca}".strip(" |")[:1000]


def _obtener_preferencias_default() -> Dict[str, Any]:
    try:
        from services.correo_argentino_operacion import obtener_preferencias_operativas_correo
        return obtener_preferencias_operativas_correo()
    except Exception:
        return {}


def _obtener_sucursales_default(pedido: Any) -> List[Dict[str, Any]]:
    from modules.transportes.correo_argentino import obtener_sucursales_correo_por_pedido
    return obtener_sucursales_correo_por_pedido(pedido)


def recalcular_sucursales_correo_operativo(
    pedido: Any,
    *,
    obtener_sucursales_fn: Optional[Callable[[Any], Iterable[Dict[str, Any]]]] = None,
    preferencias: Optional[Dict[str, Any]] = None,
    limpiar_sucursal_si_no_coincide: bool = True,
    now_fn: Optional[Callable[[], datetime]] = None,
) -> Dict[str, Any]:
    if not pedido:
        return {
            "ok": False,
            "motivo": "sin_pedido",
            "sucursales": [],
            "sucursal_limpiada": False,
        }

    obtener_sucursales_fn = obtener_sucursales_fn or _obtener_sucursales_default
    preferencias = preferencias or _obtener_preferencias_default()
    now_fn = now_fn or (lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    try:
        limite = int(preferencias.get("cantidad_sucursales_cliente") or 3)
    except Exception:
        limite = 3

    limite = max(1, min(limite, 10))

    try:
        sucursales = list(obtener_sucursales_fn(pedido) or [])
    except Exception as e:
        _agregar_resumen(pedido, f"CORREO RECALCULO: error obteniendo sucursales ({e})")
        return {
            "ok": False,
            "motivo": f"error_obteniendo_sucursales: {e}",
            "sucursales": [],
            "sucursal_limpiada": False,
        }

    sucursales = [s for s in sucursales if isinstance(s, dict)]
    seleccionadas = sucursales[:limite]

    if not seleccionadas:
        try:
            pedido.correo_sucursales_ofrecidas = "[]"
        except Exception:
            pass

        _agregar_resumen(pedido, "CORREO RECALCULO: sin sucursales cercanas confiables")

        return {
            "ok": False,
            "motivo": "sin_sucursales_cercanas",
            "sucursales": [],
            "sucursal_limpiada": False,
        }

    sucursal_actual = _texto(getattr(pedido, "sucursal_nombre", ""))
    sucursal_limpiada = False

    if limpiar_sucursal_si_no_coincide and sucursal_actual:
        coincide = any(_coincide_sucursal(sucursal_actual, suc) for suc in seleccionadas)
        if not coincide:
            try:
                pedido.sucursal_nombre = ""
                sucursal_limpiada = True
            except Exception:
                pass

    try:
        pedido.correo_sucursales_ofrecidas = json.dumps(seleccionadas, ensure_ascii=False)
    except Exception:
        pass

    try:
        pedido.empresa_envio = "Correo Argentino"
        pedido.tipo_entrega = "Sucursal"
    except Exception:
        pass

    try:
        pedido.wa_ultimo_contacto = now_fn()
    except Exception:
        pass

    nombres = ", ".join(_nombre_sucursal(s) or _id_sucursal(s) or "Punto Correo" for s in seleccionadas)
    marca = f"CORREO RECALCULO: opciones actualizadas ({nombres})"
    if sucursal_limpiada:
        marca += ". Se limpió sucursal previa por no coincidir con el nuevo cálculo."

    _agregar_resumen(pedido, marca)

    return {
        "ok": True,
        "motivo": "recalculado",
        "sucursales": seleccionadas,
        "sucursal_limpiada": sucursal_limpiada,
    }
