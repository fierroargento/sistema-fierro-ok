"""Job diario de consulta y preparación de ajustes por IPC."""

import json
import time
from urllib.error import URLError


ERRORES_TRANSITORIOS_IPC = (
    TimeoutError,
    URLError,
    ConnectionError,
    json.JSONDecodeError,
    UnicodeDecodeError,
)


def ejecutar_tareas_ipc_resilientes(
    *,
    ejecutar_ciclo_fn,
    generar_recurrente_fn,
    modelos,
    db_session,
    intentos=2,
    espera_segundos=3,
    sleep_fn=time.sleep,
    logger_fn=print,
):
    """Reintenta la consulta IPC sin bloquear las obligaciones recurrentes."""
    intentos = max(1, int(intentos))
    ipc_actualizado = False

    for intento in range(1, intentos + 1):
        try:
            ejecutar_ciclo_fn(
                modelos=modelos,
                db_session=db_session,
            )
            ipc_actualizado = True
            break
        except ERRORES_TRANSITORIOS_IPC as error:
            db_session.rollback()
            logger_fn(
                "[SCHEDULER IPC] Consulta externa fallida "
                f"({intento}/{intentos}): "
                f"{type(error).__name__}: {error}"
            )
            if intento < intentos:
                sleep_fn(espera_segundos)

    obligaciones_generadas = generar_recurrente_fn(
        ReglaObligacionCostoProductivo=(
            modelos["ReglaObligacionCostoProductivo"]
        ),
        ObligacionCostoProductivo=(
            modelos["ObligacionCostoProductivo"]
        ),
        CostoFijoVersion=modelos["CostoFijoVersion"],
        db_session=db_session,
    )

    return {
        "ipc_actualizado": ipc_actualizado,
        "obligaciones_generadas": obligaciones_generadas,
    }


def ejecutar_job_ipc_costos(app, db):
    try:
        with app.app_context():
            from models.ajuste_ipc_productivo import (
                IndiceIPCOficial,
                PropuestaAjusteIPCProductivo,
                ReglaAjusteIPCProductivo,
            )
            from models.fuentes_costo_productivo import CostoFijoVersion
            from models.cuentas_pagar_productivas import (
                ObligacionCostoProductivo,
                ReglaObligacionCostoProductivo,
            )
            from services.cuentas_pagar_productivas import (
                ejecutar_generacion_recurrente,
            )
            from services.ajustes_costos_ipc import ejecutar_ciclo_ipc

            modelos = {
                "IndiceIPCOficial": IndiceIPCOficial,
                "ReglaAjusteIPCProductivo": ReglaAjusteIPCProductivo,
                "PropuestaAjusteIPCProductivo": PropuestaAjusteIPCProductivo,
                "CostoFijoVersion": CostoFijoVersion,
                "ObligacionCostoProductivo": ObligacionCostoProductivo,
                "ReglaObligacionCostoProductivo": (
                    ReglaObligacionCostoProductivo
                ),
            }

            return ejecutar_tareas_ipc_resilientes(
                ejecutar_ciclo_fn=ejecutar_ciclo_ipc,
                generar_recurrente_fn=ejecutar_generacion_recurrente,
                modelos=modelos,
                db_session=db.session,
                logger_fn=app.logger.warning,
            )
    finally:
        try:
            db.session.remove()
        except Exception:
            pass
