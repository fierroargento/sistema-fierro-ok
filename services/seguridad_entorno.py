"""Frontera central para impedir efectos externos accidentales."""

import os


VALORES_TRUE = {"1", "true", "si", "sí", "yes", "on"}
ENTORNOS_CONECTABLES = {"staging", "produccion"}


def _activo(nombre, default="false"):
    return str(os.getenv(nombre, default) or "").strip().lower() in VALORES_TRUE


def entorno_actual():
    valor = str(os.getenv("SISTEMA_FIERRO_ENTORNO", "desarrollo") or "").strip().lower()
    return valor if valor in {"desarrollo", "staging", "produccion"} else "desarrollo"


def efectos_externos_habilitados(canal):
    canal = str(canal or "").strip().upper()
    return (
        entorno_actual() in ENTORNOS_CONECTABLES
        and _activo("EFECTOS_EXTERNOS_HABILITADOS")
        and _activo(f"{canal}_EFECTOS_HABILITADOS")
    )


def procesamiento_webhook_habilitado(canal):
    canal = str(canal or "").strip().upper()
    return (
        entorno_actual() in ENTORNOS_CONECTABLES
        and _activo("WEBHOOKS_HABILITADOS")
        and _activo(f"{canal}_WEBHOOK_HABILITADO")
    )


def scheduler_habilitado():
    return entorno_actual() in ENTORNOS_CONECTABLES and _activo("SCHEDULER_ENABLED")


def bootstrap_base_habilitado():
    return _activo("BOOTSTRAP_BASE_DATOS_HABILITADO")


def exigir_efecto_externo(canal, operacion="operacion externa"):
    if not efectos_externos_habilitados(canal):
        raise RuntimeError(
            f"{operacion} bloqueada: Sistema Fierro esta en modo desconectado "
            f"para {str(canal or '').upper()}."
        )
