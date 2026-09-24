"""Frontera central para impedir efectos externos accidentales."""

import os


VALORES_TRUE = {"1", "true", "si", "sí", "yes", "on"}
ENTORNOS_CONECTABLES = {"staging", "produccion"}


def _activo(nombre, default="false"):
    return str(os.getenv(nombre, default) or "").strip().lower() in VALORES_TRUE


def entorno_actual():
    valor = str(os.getenv("SISTEMA_FIERRO_ENTORNO", "desarrollo") or "").strip().lower()
    return valor if valor in {"desarrollo", "staging", "produccion"} else "desarrollo"


def laboratorio_forzado():
    """Candado superior: ninguna otra llave puede abrir red o automatizaciones."""
    return _activo("MODO_LABORATORIO_DESCONECTADO")


def conexiones_externas_habilitadas(canal):
    """Autoriza red saliente solo con doble habilitacion explicita."""
    canal = str(canal or "").strip().upper()
    return (not laboratorio_forzado()) and (
        entorno_actual() in ENTORNOS_CONECTABLES
        and _activo("CONEXIONES_EXTERNAS_HABILITADAS")
        and _activo(f"{canal}_CONEXION_HABILITADA")
    )


def efectos_externos_habilitados(canal):
    canal = str(canal or "").strip().upper()
    return (not laboratorio_forzado()) and (
        entorno_actual() in ENTORNOS_CONECTABLES
        and _activo("EFECTOS_EXTERNOS_HABILITADOS")
        and _activo(f"{canal}_EFECTOS_HABILITADOS")
    )


def procesamiento_webhook_habilitado(canal):
    canal = str(canal or "").strip().upper()
    return (not laboratorio_forzado()) and (
        entorno_actual() in ENTORNOS_CONECTABLES
        and _activo("WEBHOOKS_HABILITADOS")
        and _activo(f"{canal}_WEBHOOK_HABILITADO")
    )


def scheduler_habilitado():
    return (not laboratorio_forzado()) and entorno_actual() in ENTORNOS_CONECTABLES and _activo("SCHEDULER_ENABLED")


def bootstrap_base_habilitado():
    return (not laboratorio_forzado()) and _activo("BOOTSTRAP_BASE_DATOS_HABILITADO")


def operaciones_masivas_habilitadas():
    """Los resets destructivos sólo pueden abrirse expresamente en staging."""
    return (
        not laboratorio_forzado()
        and entorno_actual() == "staging"
        and _activo("OPERACIONES_MASIVAS_HABILITADAS")
    )


def exigir_efecto_externo(canal, operacion="operacion externa"):
    if not efectos_externos_habilitados(canal):
        raise RuntimeError(
            f"{operacion} bloqueada: Sistema Fierro esta en modo desconectado "
            f"para {str(canal or '').upper()}."
        )


def exigir_conexion_externa(canal, operacion="conexion externa"):
    if not conexiones_externas_habilitadas(canal):
        raise RuntimeError(
            f"{operacion} bloqueada: Sistema Fierro esta en laboratorio "
            f"desconectado para {str(canal or '').upper()}."
        )


def diagnostico_laboratorio_desconectado(canales=None):
    canales = canales or (
        "ML", "TN", "WHATSAPP", "OPENAI", "CLOUDINARY",
        "ANDREANI", "CORREO", "TRACKING", "GEOCODING", "DESCARGAS",
        "IPC", "SENTRY",
    )
    detalle = {
        canal: {
            "conexion": conexiones_externas_habilitadas(canal),
            "efectos": efectos_externos_habilitados(canal),
            "webhook": procesamiento_webhook_habilitado(canal),
        }
        for canal in canales
    }
    return {
        "entorno": entorno_actual(),
        "laboratorio_forzado": laboratorio_forzado(),
        "scheduler": scheduler_habilitado(),
        "bootstrap_base": bootstrap_base_habilitado(),
        "operaciones_masivas": operaciones_masivas_habilitadas(),
        "canales": detalle,
        "desconectado": all(
            not valor
            for estado in detalle.values()
            for valor in estado.values()
        ) and not scheduler_habilitado() and not operaciones_masivas_habilitadas(),
    }
