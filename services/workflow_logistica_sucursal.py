from __future__ import annotations

from typing import Any


def normalizar_sucursal_operativa(sucursal: dict[str, Any] | None) -> dict[str, Any]:
    sucursal = dict(sucursal or {})

    raw = sucursal.get("raw")
    if isinstance(raw, dict):
        base = dict(raw)
        base.update({k: v for k, v in sucursal.items() if k != "raw" and v not in (None, "")})
        sucursal = base

    return {
        "id": sucursal.get("id") or sucursal.get("agencyId") or sucursal.get("codigo"),
        "nombre": sucursal.get("nombre") or sucursal.get("name") or sucursal.get("descripcion") or "",
        "direccion": sucursal.get("direccion") or sucursal.get("address") or sucursal.get("domicilio") or "",
        "localidad": sucursal.get("localidad") or sucursal.get("city") or "",
        "provincia": sucursal.get("provincia") or sucursal.get("province") or "",
        "cp": sucursal.get("cp") or sucursal.get("codigo_postal") or sucursal.get("postalCode") or "",
    }


def aplicar_sucursal_elegida_al_pedido(
    pedido: Any,
    sucursal: dict[str, Any] | None,
    *,
    transporte: str = "",
    limpiar_ofrecidas: bool = True,
    limpiar_flags_ia: bool = True,
) -> bool:
    """
    Aplica datos logisticos de sucursal al pedido.

    No hace commit.
    No envia mensajes.
    No decide canal.
    No dispara cross-sell.
    """

    if not pedido or not sucursal:
        return False

    datos = normalizar_sucursal_operativa(sucursal)

    if not datos.get("nombre"):
        return False

    pedido.sucursal_nombre = datos.get("nombre")
    pedido.direccion = datos.get("direccion")
    pedido.localidad = datos.get("localidad")
    pedido.provincia = datos.get("provincia")

    if datos.get("cp") and hasattr(pedido, "codigo_postal"):
        pedido.codigo_postal = datos.get("cp")

    transporte = str(transporte or "").strip()
    if transporte and not str(getattr(pedido, "empresa_envio", "") or "").strip():
        pedido.empresa_envio = transporte

    pedido.tipo_entrega = "Sucursal"

    if limpiar_ofrecidas:
        if hasattr(pedido, "ia_sucursales_ofrecidas"):
            pedido.ia_sucursales_ofrecidas = None
        if hasattr(pedido, "correo_sucursales_ofrecidas"):
            pedido.correo_sucursales_ofrecidas = None

    if limpiar_flags_ia:
        if hasattr(pedido, "ia_requiere_operador"):
            pedido.ia_requiere_operador = False
        if hasattr(pedido, "ia_esperando_respuesta"):
            pedido.ia_esperando_respuesta = False
        if hasattr(pedido, "ml_mensajes_pendientes"):
            pedido.ml_mensajes_pendientes = False

    return True
