"""Job diario de consulta y preparación de ajustes por IPC."""


def ejecutar_job_ipc_costos(app, db):
    with app.app_context():
        from models.ajuste_ipc_productivo import (
            IndiceIPCOficial, PropuestaAjusteIPCProductivo,
            ReglaAjusteIPCProductivo,
        )
        from models.fuentes_costo_productivo import CostoFijoVersion
        from services.ajustes_costos_ipc import ejecutar_ciclo_ipc

        ejecutar_ciclo_ipc(
            modelos={
                "IndiceIPCOficial": IndiceIPCOficial,
                "ReglaAjusteIPCProductivo": ReglaAjusteIPCProductivo,
                "PropuestaAjusteIPCProductivo": PropuestaAjusteIPCProductivo,
                "CostoFijoVersion": CostoFijoVersion,
            },
            db_session=db.session,
        )
