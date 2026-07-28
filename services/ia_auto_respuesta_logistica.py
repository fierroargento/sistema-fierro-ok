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


@dataclass(frozen=True)
class ResultadoDatosCompletosAutoRespuestaMl:
    ok: bool
    motivo: str


def procesar_datos_completos_auto_respuesta_ml(
    pedido: Any,
    *,
    es_ml_acordas_fn,
    pedido_es_plegable_fn,
    preparar_asignacion_fn,
    construir_marca_revision_fn,
    agregar_marca_resumen_fn,
    aplicar_default_fn,
    sugerir_sucursales_fn,
    puede_enviar_mensaje_fn,
    enviar_mensaje_ml_fn,
    registrar_envio_automatico_fn,
    ia_hash_texto_fn,
    wa_auto_iniciar_fn,
    db_session,
    now_fn,
    log_fn=print,
    procesar_asignacion_service_fn=None,
    aplicar_default_service_fn=None,
    enviar_sugerencia_service_fn=None,
):
    """
    Coordina el camino de datos completos:
    transporte, default, sucursales y handoff.
    """
    if procesar_asignacion_service_fn is None:
        procesar_asignacion_service_fn = (
            procesar_asignacion_transporte_pp6040
        )

    if aplicar_default_service_fn is None:
        aplicar_default_service_fn = (
            aplicar_default_via_cargo_auto_respuesta
        )

    if enviar_sugerencia_service_fn is None:
        from services.ml_sucursales_via_cargo import (
            enviar_sugerencia_sucursales_ml,
        )

        enviar_sugerencia_service_fn = (
            enviar_sugerencia_sucursales_ml
        )

    pp6040_transporte_asignado = False
    es_via_cargo_acordas = bool(
        es_ml_acordas_fn(pedido)
        and not pedido_es_plegable_fn(pedido)
    )

    if not es_via_cargo_acordas:
        resultado_asignacion = (
            procesar_asignacion_service_fn(
                pedido,
                pedido_es_plegable_fn=(
                    pedido_es_plegable_fn
                ),
                preparar_asignacion_fn=(
                    preparar_asignacion_fn
                ),
                construir_marca_revision_fn=(
                    construir_marca_revision_fn
                ),
                agregar_marca_resumen_fn=(
                    agregar_marca_resumen_fn
                ),
                db_session=db_session,
                log_fn=log_fn,
            )
        )
        pp6040_transporte_asignado = bool(
            resultado_asignacion.transporte_asignado
        )

        if not pp6040_transporte_asignado:
            return ResultadoDatosCompletosAutoRespuestaMl(
                ok=False,
                motivo=(
                    resultado_asignacion.motivo
                    or "datos_completos"
                ),
            )

    if not pp6040_transporte_asignado:
        aplicar_default_service_fn(
            pedido,
            aplicar_default_fn=aplicar_default_fn,
            db_session=db_session,
            log_fn=log_fn,
        )

    resultado_sucursales = enviar_sugerencia_service_fn(
        pedido=pedido,
        sugerir_sucursales_fn=sugerir_sucursales_fn,
        puede_enviar_mensaje_fn=(
            puede_enviar_mensaje_fn
        ),
        enviar_mensaje_ml_fn=enviar_mensaje_ml_fn,
        registrar_envio_automatico_fn=(
            registrar_envio_automatico_fn
        ),
        ia_hash_texto_fn=ia_hash_texto_fn,
        db_session=db_session,
        motivo_ok="sucursales_enviadas",
        motivo_error="error_sucursales",
        now_fn=now_fn,
        log_fn=log_fn,
    )

    if resultado_sucursales is not None:
        return ResultadoDatosCompletosAutoRespuestaMl(
            ok=bool(resultado_sucursales["ok"]),
            motivo=resultado_sucursales["motivo"],
        )

    ok_wa, motivo_wa = wa_auto_iniciar_fn(
        pedido,
        faltantes=[],
        motivo=(
            "ia_auto_responder_post_analisis_"
            "datos_completos"
        ),
    )

    if ok_wa:
        return ResultadoDatosCompletosAutoRespuestaMl(
            ok=True,
            motivo="wa_iniciado_datos_completos",
        )

    return ResultadoDatosCompletosAutoRespuestaMl(
        ok=False,
        motivo=motivo_wa or "datos_completos",
    )
