import os

from dataclasses import dataclass

from services.wa_auto_ml_decision import (
    construir_log_error_wa_auto_ml,
)


@dataclass(frozen=True)
class ResultadoHabilitacionAutoRespuestaMl:
    habilitada: bool
    motivo: str


def evaluar_habilitacion_auto_respuesta_ml(
    pedido,
    *,
    es_pedido_aplicable_fn,
):
    """Evalua las precondiciones generales del flujo."""

    configuracion = str(
        os.getenv("IA_AUTO_RESPUESTA", "1") or ""
    ).strip().lower()

    if configuracion in {"0", "false", "no", "off"}:
        return ResultadoHabilitacionAutoRespuestaMl(
            habilitada=False,
            motivo="apagada",
        )

    if (
        not pedido
        or not es_pedido_aplicable_fn(pedido)
    ):
        return ResultadoHabilitacionAutoRespuestaMl(
            habilitada=False,
            motivo="no_aplica",
        )

    if not getattr(
        pedido,
        "contacto_iniciado",
        False,
    ):
        return ResultadoHabilitacionAutoRespuestaMl(
            habilitada=False,
            motivo="sin_contacto",
        )

    if (
        str(
            getattr(
                pedido,
                "ia_recolector_estado",
                "",
            )
            or ""
        )
        == "error"
    ):
        return ResultadoHabilitacionAutoRespuestaMl(
            habilitada=False,
            motivo="error_ia",
        )

    return ResultadoHabilitacionAutoRespuestaMl(
        habilitada=True,
        motivo="habilitada",
    )


@dataclass(frozen=True)
class ResultadoEnvioAutoRespuestaMl:
    ok: bool
    motivo: str


def enviar_auto_respuesta_ml(
    pedido,
    texto,
    *,
    requiere_operador,
    faltantes,
    respuesta_ya_enviada_fn,
    puede_enviar_fn,
    enviar_mensaje_fn,
    registrar_envio_fn,
    hash_texto_fn,
    ahora_fn,
    log_fn=print,
):
    """
    Valida, envía y registra la respuesta automática
    general de ML. No realiza commits.
    """
    texto = str(texto or "").strip()

    if not texto:
        return ResultadoEnvioAutoRespuestaMl(
            ok=False,
            motivo="sin_texto",
        )

    if respuesta_ya_enviada_fn(
        pedido,
        texto,
    ):
        return ResultadoEnvioAutoRespuestaMl(
            ok=False,
            motivo="duplicada",
        )

    try:
        permitido, motivo = puede_enviar_fn(
            pedido=pedido,
            canal="ml",
            texto=texto,
        )

        if not permitido:
            log_fn(
                "[CANAL-MANAGER] ML bloqueado "
                f"pedido #{pedido.id}: {motivo}"
            )
            return ResultadoEnvioAutoRespuestaMl(
                ok=False,
                motivo=motivo,
            )

        enviar_mensaje_fn(
            pedido,
            texto,
            permitir_requiere_operador=bool(
                requiere_operador
                and faltantes
            ),
        )

        registrar_envio_fn(
            pedido=pedido,
            canal="ml",
            texto=texto,
        )

        pedido.ia_respuesta_sugerida = texto
        pedido.ia_respuesta_enviada_hash = (
            hash_texto_fn(texto)
        )
        pedido.ia_ultima_respuesta_enviada = (
            ahora_fn()
        )

        if requiere_operador:
            pedido.ia_requiere_operador = True
            pedido.ia_recolector_estado = (
                "requiere_operador"
            )
            pedido.ml_mensajes_pendientes = True
            pedido.ml_mensajes_pendientes_count = max(
                int(
                    pedido.ml_mensajes_pendientes_count
                    or 0
                ),
                1,
            )
            pedido.ia_resumen = (
                (pedido.ia_resumen or "")
                + " | IA respondió y dejó consulta "
                "pendiente para operador"
            ).strip(" |")

        else:
            pedido.ml_mensajes_pendientes = False
            pedido.ml_mensajes_pendientes_count = 0
            pedido.ia_resumen = (
                (pedido.ia_resumen or "")
                + " | IA respondió automáticamente"
            ).strip(" |")

        log_fn(
            "[IA-AUTO-RESPUESTA] OK pedido "
            f"#{pedido.id}: {texto[:120]}"
        )

        return ResultadoEnvioAutoRespuestaMl(
            ok=True,
            motivo="enviada",
        )

    except Exception as error:
        pedido.ia_error = (
            "No se pudo enviar respuesta "
            "automática IA: "
            f"{str(error)[:400]}"
        )
        log_fn(
            construir_log_error_wa_auto_ml(
                getattr(pedido, "id", ""),
                error,
            )
        )

        return ResultadoEnvioAutoRespuestaMl(
            ok=False,
            motivo="error_envio",
        )
