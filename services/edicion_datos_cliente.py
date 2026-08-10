"""Edición operativa limitada de datos usados para confeccionar etiquetas."""

from dataclasses import dataclass
from typing import Any, Callable, Mapping


ESTADOS_EDITABLES_ANTES_ETIQUETA = {
    "Cargando Pedido",
    "Etiqueta Lista",
}

CAMPOS_DATOS_CLIENTE = (
    "cliente",
    "dni",
    "telefono",
    "mail",
    "direccion",
    "localidad",
    "provincia",
    "codigo_postal",
    "sucursal_nombre",
    "autorizado_nombre",
    "autorizado_dni",
    "autorizado_telefono",
)


@dataclass(frozen=True)
class ResultadoEdicionDatosCliente:
    permitida: bool
    cambios: tuple[str, ...] = ()
    motivo: str = ""


def puede_editar_datos_cliente_para_etiqueta(
    pedido: Any,
    *,
    rol: str,
) -> bool:
    if not pedido or str(rol or "").lower() not in {"admin", "carga"}:
        return False

    if getattr(pedido, "fecha_etiqueta_impresa", None):
        return False

    return str(getattr(pedido, "estado", "") or "") in (
        ESTADOS_EDITABLES_ANTES_ETIQUETA
    )


def aplicar_edicion_datos_cliente_para_etiqueta(
    pedido: Any,
    datos: Mapping[str, Any],
    *,
    rol: str,
    normalizar_telefono_fn: Callable[[Any], str],
) -> ResultadoEdicionDatosCliente:
    if not puede_editar_datos_cliente_para_etiqueta(pedido, rol=rol):
        return ResultadoEdicionDatosCliente(
            permitida=False,
            motivo="edicion_fuera_de_etapa_o_rol",
        )

    cambios = []
    for campo in CAMPOS_DATOS_CLIENTE:
        valor_nuevo = str(datos.get(campo) or "").strip()
        if campo in {"telefono", "autorizado_telefono"}:
            valor_nuevo = normalizar_telefono_fn(valor_nuevo) if valor_nuevo else ""

        valor_anterior = str(getattr(pedido, campo, "") or "").strip()
        if valor_nuevo == valor_anterior:
            continue

        setattr(pedido, campo, valor_nuevo)
        cambios.append(campo)

    if "cliente" in cambios and hasattr(pedido, "ml_nombre_real"):
        pedido.ml_nombre_real = True

    return ResultadoEdicionDatosCliente(
        permitida=True,
        cambios=tuple(cambios),
        motivo="actualizado" if cambios else "sin_cambios",
    )
