"""
services/ml_consultas_logisticas.py
──────────────────────────────────
Consultas logísticas simples de ML/Acordás que el bot sí puede responder.

APB:
- "Cuánto demora" no debe escalar a operador si es una consulta simple.
- Reclamos, enojo, cancelaciones, problemas o cambios de modalidad siguen yendo a operador.
"""

from dataclasses import dataclass

import unicodedata


def _normalizar(valor):
    texto = str(valor or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(ch for ch in texto if unicodedata.category(ch) != "Mn")
    return " ".join(texto.split())


def detectar_consulta_demora_simple_ml(pedido):
    if not pedido:
        return False

    resumen = _normalizar(getattr(pedido, "ia_resumen", ""))

    if not resumen:
        return False

    menciona_demora = any(
        marca in resumen
        for marca in [
            "pregunta por demora",
            "pregunta demora",
            "cuanto demora",
            "cuanto tarda",
            "cuando llega",
            "cuando llegaria",
            "tiempo de entrega",
            "demora habitual",
        ]
    )

    if not menciona_demora:
        return False

    bloqueadores_operador = [
        "reclamo",
        "problema",
        "enojo",
        "insulto",
        "cancel",
        "devolucion",
        "producto roto",
        "producto incorrecto",
        "no llego",
        "llego tarde",
        "cambio de modalidad",
        "retirar personalmente",
        "retiro",
    ]

    return not any(marca in resumen for marca in bloqueadores_operador)


def texto_demora_handoff_wa_ml():
    return (
        "La demora habitual es de entre 3 y 5 días hábiles a partir del despacho.\n\n"
        "Para seguir con la coordinación del envío, en breve te vamos a escribir por WhatsApp."
    )


def limpiar_derivacion_operador_por_demora_simple(pedido):
    if not detectar_consulta_demora_simple_ml(pedido):
        return False

    try:
        pedido.ia_requiere_operador = False
    except Exception:
        pass

    try:
        if str(getattr(pedido, "ia_recolector_estado", "") or "").strip().lower() == "requiere_operador":
            pedido.ia_recolector_estado = "datos_completos"
    except Exception:
        pass

    return True


@dataclass(frozen=True)
class ResultadoConsultaDemoraMl:
    procesada: bool
    ok: bool = False
    motivo: str = ""


def procesar_consulta_demora_simple_ml(
    pedido,
    faltantes,
    *,
    es_ml_acordas_fn,
    pedido_es_plegable_fn,
    bloquea_inicio_wa_fn,
    respuesta_ya_enviada_fn,
    puede_enviar_fn,
    enviar_mensaje_fn,
    registrar_envio_fn,
    hash_texto_fn,
    ahora_fn,
    wa_auto_iniciar_fn,
    db_session,
    log_fn=print,
):
    """
    Responde una consulta simple de demora con datos
    completos y luego intenta continuar por WhatsApp.
    """
    debe_priorizar_sucursal = bool(
        es_ml_acordas_fn(pedido)
        and not str(
            getattr(pedido, "sucursal_nombre", "")
            or ""
        ).strip()
        and (
            pedido_es_plegable_fn(pedido)
            or bloquea_inicio_wa_fn(pedido)
            or str(
                getattr(pedido, "wa_estado", "")
                or ""
            ).strip().lower()
            == "falta_elegir_transporte"
            or bool(
                getattr(
                    pedido,
                    "ia_sucursales_ofrecidas",
                    None,
                )
                or getattr(
                    pedido,
                    "correo_sucursales_ofrecidas",
                    None,
                )
            )
        )
    )

    if (
        faltantes
        or not detectar_consulta_demora_simple_ml(
            pedido
        )
        or debe_priorizar_sucursal
    ):
        return ResultadoConsultaDemoraMl(
            procesada=False,
        )

    texto_demora = texto_demora_handoff_wa_ml()

    if respuesta_ya_enviada_fn(
        pedido,
        texto_demora,
    ):
        return ResultadoConsultaDemoraMl(
            procesada=True,
            ok=False,
            motivo="duplicada",
        )

    try:
        limpiar_derivacion_operador_por_demora_simple(
            pedido
        )

        permitido, motivo = puede_enviar_fn(
            pedido=pedido,
            canal="ml",
            texto=texto_demora,
        )

        if not permitido:
            return ResultadoConsultaDemoraMl(
                procesada=True,
                ok=False,
                motivo=motivo,
            )

        enviar_mensaje_fn(
            pedido,
            texto_demora,
        )

        registrar_envio_fn(
            pedido=pedido,
            canal="ml",
            texto=texto_demora,
        )

        pedido.ia_respuesta_sugerida = texto_demora
        pedido.ia_respuesta_enviada_hash = (
            hash_texto_fn(texto_demora)
        )
        pedido.ia_ultima_respuesta_enviada = (
            ahora_fn()
        )
        pedido.ml_mensajes_pendientes = False
        pedido.ml_mensajes_pendientes_count = 0

        from services.ml_wa_handoff import (
            marcar_transicion_ml_wa_en_resumen,
        )

        marcar_transicion_ml_wa_en_resumen(pedido)

        db_session.commit()

    except Exception as error:
        log_fn(
            "[ML-DEMORA] No se pudo responder "
            "demora y pasar a WA pedido "
            f"#{getattr(pedido, 'id', '?')}: "
            f"{error}"
        )

        try:
            db_session.rollback()
        except Exception:
            pass

        return ResultadoConsultaDemoraMl(
            procesada=True,
            ok=False,
            motivo="error_demora_ml",
        )

    ok_wa, motivo_wa = wa_auto_iniciar_fn(
        pedido,
        faltantes=[],
        motivo="consulta_demora_datos_completos",
    )

    if ok_wa:
        return ResultadoConsultaDemoraMl(
            procesada=True,
            ok=True,
            motivo="demora_respondida_wa_iniciado",
        )

    return ResultadoConsultaDemoraMl(
        procesada=True,
        ok=True,
        motivo=(
            "demora_respondida_"
            f"{motivo_wa or 'wa_no_iniciado'}"
        ),
    )
