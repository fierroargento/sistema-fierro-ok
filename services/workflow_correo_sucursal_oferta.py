from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OfertaSucursalesCorreo:
    sucursales: list[dict[str, Any]]
    ids: list[str]
    mensaje: str


def normalizar_sucursal_correo_oferta(sucursal: dict[str, Any] | None, indice: int = 0) -> dict[str, Any]:
    sucursal = dict(sucursal or {})

    return {
        "id": str(
            sucursal.get("id")
            or sucursal.get("agencyId")
            or sucursal.get("codigo")
            or indice + 1
        ),
        "nombre": sucursal.get("nombre") or sucursal.get("name") or sucursal.get("descripcion") or "Punto Correo",
        "direccion": sucursal.get("direccion") or sucursal.get("address") or sucursal.get("domicilio") or "",
        "localidad": sucursal.get("localidad") or sucursal.get("city") or "",
        "provincia": sucursal.get("provincia") or sucursal.get("province") or "",
        "cp": sucursal.get("cp") or sucursal.get("codigo_postal") or sucursal.get("postalCode") or "",
        "raw": sucursal,
    }


def seleccionar_sucursales_correo_oferta(
    sucursales: list[dict[str, Any]] | None,
    limite: int = 3,
) -> list[dict[str, Any]]:
    try:
        limite = int(limite or 3)
    except Exception:
        limite = 3

    if limite <= 0:
        limite = 3

    salida = []
    for indice, sucursal in enumerate((sucursales or [])[:limite]):
        salida.append(normalizar_sucursal_correo_oferta(sucursal, indice))

    return salida


def ids_sucursales_correo_oferta(sucursales: list[dict[str, Any]] | None) -> list[str]:
    ids = []
    for indice, sucursal in enumerate(sucursales or []):
        datos = normalizar_sucursal_correo_oferta(sucursal, indice)
        ids.append(datos["id"])
    return ids


def armar_mensaje_sucursales_correo(sucursales: list[dict[str, Any]] | None) -> str:
    sucursales_normalizadas = [
        normalizar_sucursal_correo_oferta(s, i)
        for i, s in enumerate(sucursales or [])
    ]

    if not sucursales_normalizadas:
        return ""

    lista = ""
    for i, sucursal in enumerate(sucursales_normalizadas, 1):
        nombre = sucursal["nombre"]
        direccion = sucursal["direccion"]
        localidad = sucursal["localidad"]
        lista += f"{i}) {nombre}\n{direccion}{(' - ' + localidad) if localidad else ''}\n\n"

    return (
        "Genial, ya tenemos los datos para avanzar con el despacho.\n\n"
        "Siempre recomendamos retiro en sucursal o punto Correo porque suele ser más ordenado "
        "y evita posibles demoras por visitas fallidas en domicilio.\n\n"
        "Te paso las opciones más cercanas:\n\n"
        f"{lista}"
        "Decime cuál preferís y seguimos con el despacho."
    )


def preparar_oferta_sucursales_correo(
    sucursales: list[dict[str, Any]] | None,
    limite: int = 3,
) -> OfertaSucursalesCorreo | None:
    seleccionadas = seleccionar_sucursales_correo_oferta(sucursales, limite=limite)

    if not seleccionadas:
        return None

    return OfertaSucursalesCorreo(
        sucursales=seleccionadas,
        ids=ids_sucursales_correo_oferta(seleccionadas),
        mensaje=armar_mensaje_sucursales_correo(seleccionadas),
    )
