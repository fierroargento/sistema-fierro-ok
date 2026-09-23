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

LIMITES_DATOS_CLIENTE = {
    "cliente": 120,
    "dni": 20,
    "telefono": 30,
    "mail": 120,
    "direccion": 200,
    "localidad": 100,
    "provincia": 100,
    "codigo_postal": 10,
    "sucursal_nombre": 150,
    "autorizado_nombre": 120,
    "autorizado_dni": 20,
    "autorizado_telefono": 30,
}


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
    organizacion_id: int,
    unidad_negocio_id: int,
    normalizar_telefono_fn: Callable[[Any], str],
) -> ResultadoEdicionDatosCliente:
    if (
        getattr(pedido, "organizacion_id", None) != int(organizacion_id)
        or getattr(pedido, "unidad_negocio_id", None) != int(unidad_negocio_id)
    ):
        return ResultadoEdicionDatosCliente(
            permitida=False,
            motivo="pedido_fuera_del_contexto_activo",
        )

    if not puede_editar_datos_cliente_para_etiqueta(pedido, rol=rol):
        return ResultadoEdicionDatosCliente(
            permitida=False,
            motivo="edicion_fuera_de_etapa_o_rol",
        )

    valores_validados = {}
    for campo in CAMPOS_DATOS_CLIENTE:
        valor_nuevo = str(datos.get(campo) or "").strip()
        if campo in {"telefono", "autorizado_telefono"}:
            valor_nuevo = normalizar_telefono_fn(valor_nuevo) if valor_nuevo else ""

        if len(valor_nuevo) > LIMITES_DATOS_CLIENTE[campo]:
            return ResultadoEdicionDatosCliente(
                permitida=False,
                motivo=f"campo_demasiado_largo:{campo}",
            )

        valores_validados[campo] = valor_nuevo

    cambios = []
    for campo, valor_nuevo in valores_validados.items():

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
