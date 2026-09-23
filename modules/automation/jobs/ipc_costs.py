"""Job diario de consulta y preparación de ajustes por IPC."""

from services.seguridad_entorno import (
    conexiones_externas_habilitadas,
    scheduler_habilitado,
)


def ejecutar_job_ipc_costos(app, db):
    if not scheduler_habilitado():
        return False
    if not conexiones_externas_habilitadas("IPC"):
        return False

    with app.app_context():
        from models.ajuste_ipc_productivo import (
            IndiceIPCOficial, PropuestaAjusteIPCProductivo,
            ReglaAjusteIPCProductivo,
        )
        from models.fuentes_costo_productivo import CostoFijoVersion
        from models.cuentas_pagar_productivas import (
            ObligacionCostoProductivo, ReglaObligacionCostoProductivo,
        )
        from services.cuentas_pagar_productivas import ejecutar_generacion_recurrente
        from services.ajustes_costos_ipc import ejecutar_ciclo_ipc

        ejecutar_ciclo_ipc(
            modelos={
                "IndiceIPCOficial": IndiceIPCOficial,
                "ReglaAjusteIPCProductivo": ReglaAjusteIPCProductivo,
                "PropuestaAjusteIPCProductivo": PropuestaAjusteIPCProductivo,
                "CostoFijoVersion": CostoFijoVersion,
                "ObligacionCostoProductivo": ObligacionCostoProductivo,
            },
            db_session=db.session,
        )
        ejecutar_generacion_recurrente(
            ReglaObligacionCostoProductivo=ReglaObligacionCostoProductivo,
            ObligacionCostoProductivo=ObligacionCostoProductivo,
            CostoFijoVersion=CostoFijoVersion, db_session=db.session,
        )
    return True
