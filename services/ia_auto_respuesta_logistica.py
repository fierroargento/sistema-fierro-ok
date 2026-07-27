"""Persistencia logística previa a la auto-respuesta ML."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResultadoAsignacionTransporteAutoRespuesta:
    procesada: bool
    transporte_asignado: bool
    motivo: str = ""


def _rollback_seguro(db_session):
    try:
        db_session.rollback()
    except Exception:
        pass


def procesar_asignacion_transporte_pp6040(
    pedido: Any,
    *,
    pedido_es_plegable_fn,
    preparar_asignacion_fn,
    construir_marca_revision_fn,
    agregar_marca_resumen_fn,
    db_session,
    log_fn=print,
):
    """Interpreta y persiste la asignación PP6040."""

    if not pedido_es_plegable_fn(pedido):
        return ResultadoAsignacionTransporteAutoRespuesta(
            procesada=False,
            transporte_asignado=False,
            motivo="no_aplicable",
        )

    try:
        resultado = preparar_asignacion_fn(pedido)
        mensaje = resultado.mensaje

        if resultado.requiere_rollback:
            _rollback_seguro(db_session)

        if resultado.ok:
            resumen = str(
                getattr(pedido, "ia_resumen", "") or ""
            ).strip()
            pedido.ia_resumen = (
                f"{resumen} | {mensaje}"
            ).strip(" |")

            db_session.commit()

            log_fn(
                f"[TRANSPORTES] Pedido "
                f"#{getattr(pedido, 'id', '?')}: "
                f"{mensaje}"
            )

            return (
                ResultadoAsignacionTransporteAutoRespuesta(
                    procesada=True,
                    transporte_asignado=True,
                    motivo="transporte_asignado",
                )
            )

        pedido.ml_mensajes_pendientes = True
        pedido.ia_requiere_operador = True

        resumen = str(
            getattr(pedido, "ia_resumen", "") or ""
        ).strip()
        marca = construir_marca_revision_fn(
            getattr(pedido, "codigo_postal", ""),
            mensaje,
        )
        pedido.ia_resumen = agregar_marca_resumen_fn(
            resumen,
            marca,
            limite=1000,
        )

        db_session.commit()

        return ResultadoAsignacionTransporteAutoRespuesta(
            procesada=True,
            transporte_asignado=False,
            motivo="datos_completos",
        )

    except Exception as error:
        _rollback_seguro(db_session)
        log_fn(
            "[TRANSPORTES] Error asignando transporte "
            f"pedido #{getattr(pedido, 'id', '?')}: "
            f"{error}"
        )

        return ResultadoAsignacionTransporteAutoRespuesta(
            procesada=True,
            transporte_asignado=False,
            motivo="datos_completos",
        )


def aplicar_default_via_cargo_auto_respuesta(
    pedido: Any,
    *,
    aplicar_default_fn,
    db_session,
    log_fn=print,
) -> bool:
    """
    Aplica y persiste el default logístico previo a la
    auto-respuesta. Los errores no interrumpen el flujo.
    """
    try:
        modificado = bool(
            aplicar_default_fn(pedido)
        )

        if modificado:
            db_session.commit()

        return modificado

    except Exception as error:
        log_fn(
            "[LOGISTICA-DEFAULTS] No se pudo aplicar "
            "default Via Cargo pedido "
            f"#{getattr(pedido, 'id', '?')}: {error}"
        )
        _rollback_seguro(db_session)
        return False
