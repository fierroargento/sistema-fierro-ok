from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


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
        "cp": str(
            sucursal.get("cp")
            or sucursal.get("codigo_postal")
            or sucursal.get("postalCode")
            or ""
        ).strip(),
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


def marca_resumen_sucursal_confirmada(indice: int | None, sucursal: dict[str, Any] | None) -> str:
    """
    Construye la marca humana para ia_resumen.

    No modifica el pedido.
    No hace commit.
    No envia mensajes.
    """

    if indice is None or not sucursal:
        return ""

    nombre = str(
        sucursal.get("nombre")
        or sucursal.get("name")
        or sucursal.get("descripcion")
        or ""
    ).strip()

    if not nombre:
        return ""

    return f"Sucursal confirmada por opción {indice + 1}: {nombre}"


def agregar_marca_resumen_sucursal_confirmada(
    resumen_actual: str | None,
    indice: int | None,
    sucursal: dict[str, Any] | None,
) -> str:
    """
    Devuelve ia_resumen con la marca agregada una sola vez.

    No modifica el pedido.
    No hace commit.
    No envia mensajes.
    """

    resumen = str(resumen_actual or "").strip()
    marca = marca_resumen_sucursal_confirmada(indice, sucursal)

    if not marca:
        return resumen

    if marca in resumen:
        return resumen

    return f"{resumen} | {marca}".strip(" |")


def aplicar_decision_sucursal_al_pedido(
    pedido: Any,
    decision: Any,
    *,
    transporte: str = "",
) -> bool:
    """
    Aplica al pedido una DecisionSucursal ya resuelta.

    No detecta opciones.
    No lee catalogos.
    No hace commit.
    No envia mensajes.
    No decide canal ni cross-sell.
    """

    if (
        not pedido
        or not decision
        or not bool(
            getattr(decision, "seleccionada", False)
        )
    ):
        return False

    sucursal = getattr(decision, "sucursal", None)
    indice = getattr(decision, "indice", None)

    if not aplicar_sucursal_elegida_al_pedido(
        pedido,
        sucursal,
        transporte=transporte,
    ):
        return False

    pedido.ia_resumen = (
        agregar_marca_resumen_sucursal_confirmada(
            getattr(pedido, "ia_resumen", ""),
            indice,
            sucursal,
        )
    )

    return True

@dataclass(frozen=True)
class ResultadoAplicacionSucursalDetectada:
    aplicada: bool
    persistida: bool = False
    error_persistencia: str = ""
    errores_auxiliares: tuple[str, ...] = ()


def aplicar_y_persistir_sucursal_detectada(
    pedido: Any,
    sucursal: dict[str, Any] | None,
    *,
    db_session: Any,
    transporte_default: str = "Vía Cargo",
    limpiar_revision_fn: Callable[[Any], Any] | None = None,
    marcar_pendiente_fn: Callable[[Any], Any] | None = None,
    log_fn: Callable[[str], Any] | None = print,
) -> ResultadoAplicacionSucursalDetectada:
    """
    Aplica y persiste una sucursal detectada por el flujo legacy.

    Conserva su contrato histórico:
    - no pisa una sucursal ya confirmada;
    - no pisa un transporte existente;
    - no copia CP ni limpia opciones/flags genéricos;
    - tolera errores auxiliares y de persistencia;
    - permite continuar con la confirmación al cliente.
    """

    if (
        not pedido
        or not sucursal
        or getattr(pedido, "sucursal_nombre", None)
    ):
        return ResultadoAplicacionSucursalDetectada(
            aplicada=False,
        )

    nombre = sucursal.get("nombre")
    if not nombre:
        return ResultadoAplicacionSucursalDetectada(
            aplicada=False,
        )

    pedido.sucursal_nombre = nombre
    pedido.direccion = sucursal.get("direccion")
    pedido.localidad = sucursal.get("localidad")
    pedido.provincia = sucursal.get("provincia")

    if not str(
        getattr(pedido, "empresa_envio", "")
        or ""
    ).strip():
        pedido.empresa_envio = transporte_default

    pedido.tipo_entrega = "Sucursal"

    errores_auxiliares = []

    if limpiar_revision_fn is None:
        from services.transporte_revision import (
            limpiar_revision_correo_resuelta_por_sucursales,
        )

        limpiar_revision_fn = (
            limpiar_revision_correo_resuelta_por_sucursales
        )

    try:
        limpiar_revision_fn(pedido)
    except Exception as error:
        errores_auxiliares.append(str(error))
        if log_fn is not None:
            try:
                log_fn(
                    "[TRANSPORTE] No se pudo limpiar "
                    f"revisión Correo resuelta: {error}"
                )
            except Exception:
                pass

    if marcar_pendiente_fn is None:
        from services.correo_argentino_operacion import (
            marcar_correo_sucursal_pendiente_operador,
        )

        marcar_pendiente_fn = (
            marcar_correo_sucursal_pendiente_operador
        )

    try:
        marcar_pendiente_fn(pedido)
    except Exception as error:
        errores_auxiliares.append(str(error))
        if log_fn is not None:
            try:
                log_fn(
                    "[CORREO] No se pudo marcar "
                    f"pendiente operador: {error}"
                )
            except Exception:
                pass

    try:
        db_session.commit()
    except Exception as error:
        try:
            db_session.rollback()
        except Exception as error_rollback:
            errores_auxiliares.append(
                f"rollback: {error_rollback}"
            )
            if log_fn is not None:
                try:
                    log_fn(
                        "[SUCURSAL] No se pudo revertir "
                        f"la persistencia fallida: {error_rollback}"
                    )
                except Exception:
                    pass

        return ResultadoAplicacionSucursalDetectada(
            aplicada=False,
            persistida=False,
            error_persistencia=str(error),
            errores_auxiliares=tuple(
                errores_auxiliares
            ),
        )

    return ResultadoAplicacionSucursalDetectada(
        aplicada=True,
        persistida=True,
        errores_auxiliares=tuple(
            errores_auxiliares
        ),
    )
