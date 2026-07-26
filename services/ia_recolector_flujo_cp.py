"""
Orquestación previa de código postal y sucursal para ML.

Compone servicios especializados sin importar app.py,
Flask, modelos ni la base de datos global.
"""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ResultadoFlujoCodigoPostal:
    cp_detectado: str = ""
    finalizar_analisis: bool = False
    respuesta_analisis: Any = None


def procesar_flujo_codigo_postal_recolector(
    *,
    pedido: Any,
    texto: Any,
    texto_ultimo: Any,
    faltantes_fn: Callable[[Any], Any],
    resolver_cp_fn: Callable[..., Any],
    aplicar_cp_fn: Callable[..., Any],
    normalizar_ubicacion_fn: Callable[..., Any],
    procesar_post_cp_fn: Callable[..., Any],
    orquestar_confirmacion_temprana_fn: Callable[..., Any],
    despacho_completo_fn: Callable[..., Any],
    actualizar_estado_fn: Callable[..., Any],
    es_afirmativo_fn: Callable[..., Any],
    auto_responder_fn: Callable[..., Any],
    procesar_escalamiento_fn: Callable[..., Any],
    pedido_es_plegable_fn: Callable[..., Any],
    es_consulta_no_eleccion_fn: Callable[..., Any],
    detectar_sucursal_fn: Callable[..., Any],
    aplicar_sucursal_fn: Callable[..., Any],
    notificar_sucursal_fn: Callable[..., Any],
    puede_enviar_fn: Callable[..., Any],
    enviar_mensaje_fn: Callable[..., Any],
    registrar_envio_fn: Callable[..., Any],
    wa_auto_iniciar_fn: Callable[..., Any],
    db_session: Any,
    logger_fn: Callable[[str], Any] = print,
) -> ResultadoFlujoCodigoPostal:
    faltantes_actuales = faltantes_fn(pedido) or []

    cp_detectado = resolver_cp_fn(
        texto,
        faltantes_actuales=faltantes_actuales,
        faltantes_guardados=getattr(
            pedido,
            "ia_faltantes",
            None,
        ),
        codigo_postal_actual=getattr(
            pedido,
            "codigo_postal",
            None,
        ),
    )

    if not cp_detectado:
        return ResultadoFlujoCodigoPostal()

    aplicar_cp_fn(
        pedido,
        cp_detectado,
        normalizar_ubicacion_fn=(
            normalizar_ubicacion_fn
        ),
        faltantes_fn=faltantes_fn,
        db_session=db_session,
        logger_fn=logger_fn,
    )

    texto_sucursal = texto_ultimo or texto

    resultado_post_cp = procesar_post_cp_fn(
        pedido,
        texto_sucursal,
        orquestar_confirmacion_fn=(
            orquestar_confirmacion_temprana_fn
        ),
        despacho_completo_fn=despacho_completo_fn,
        actualizar_estado_fn=actualizar_estado_fn,
        db_session=db_session,
        es_afirmativo_fn=es_afirmativo_fn,
        auto_responder_fn=auto_responder_fn,
        logger_fn=logger_fn,
    )

    if resultado_post_cp.finalizar_analisis:
        return ResultadoFlujoCodigoPostal(
            cp_detectado=str(cp_detectado),
            finalizar_analisis=True,
            respuesta_analisis={
                "ok": True,
                "estado": "sucursal_confirmada",
                "sucursal_confirmada": True,
            },
        )

    resultado_escalamiento = procesar_escalamiento_fn(
        pedido,
        texto_sucursal,
        resultado_post_cp.confirmacion,
        pedido_es_plegable_fn=pedido_es_plegable_fn,
        es_consulta_no_eleccion_fn=(
            es_consulta_no_eleccion_fn
        ),
        db_session=db_session,
        logger_fn=logger_fn,
    )

    if resultado_escalamiento.finalizar_analisis:
        return ResultadoFlujoCodigoPostal(
            cp_detectado=str(cp_detectado),
            finalizar_analisis=True,
        )

    deteccion = resultado_escalamiento.deteccion

    if not deteccion.puede_detectar:
        return ResultadoFlujoCodigoPostal(
            cp_detectado=str(cp_detectado),
        )

    sucursal = None
    if deteccion.correo_ofrecidas:
        sucursal = detectar_sucursal_fn(
            pedido,
            texto_sucursal,
        )

    resultado_aplicacion = aplicar_sucursal_fn(
        pedido,
        sucursal,
        db_session=db_session,
        transporte_default="Vía Cargo",
        log_fn=logger_fn,
    )

    if not resultado_aplicacion.aplicada:
        return ResultadoFlujoCodigoPostal(
            cp_detectado=str(cp_detectado),
        )

    resultado_notificacion = notificar_sucursal_fn(
        pedido=pedido,
        sucursal=sucursal,
        texto_cliente=texto_sucursal,
        puede_enviar_fn=puede_enviar_fn,
        enviar_mensaje_fn=enviar_mensaje_fn,
        registrar_envio_fn=registrar_envio_fn,
        wa_auto_iniciar_fn=wa_auto_iniciar_fn,
        db_session=db_session,
        log_fn=logger_fn,
    )

    if resultado_notificacion.respuesta_flujo is not None:
        return ResultadoFlujoCodigoPostal(
            cp_detectado=str(cp_detectado),
            finalizar_analisis=True,
            respuesta_analisis=(
                resultado_notificacion
                .respuesta_flujo
            ),
        )

    return ResultadoFlujoCodigoPostal(
        cp_detectado=str(cp_detectado),
    )
