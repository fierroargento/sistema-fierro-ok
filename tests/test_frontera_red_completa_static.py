"""Toda primitiva de red conocida debe vivir detrás de la frontera central."""

from pathlib import Path


ARCHIVOS_CON_RED = (
    "app.py",
    "services/ajustes_costos_ipc.py",
    "services/andreani.py",
    "services/correo_argentino_micorreo.py",
    "services/cpa_correo.py",
    "services/ia.py",
    "services/tracking_externo.py",
    "modules/bot_ml/api_client.py",
    "modules/bot_ml/orders_api.py",
    "modules/transportes/andreani.py",
    "modules/transportes/correo_argentino.py",
    "modules/whatsapp/media_inbound.py",
    "modules/whatsapp/sender.py",
    "scripts/subir_imagenes_cross_sell_cloudinary.py",
)


def test_archivos_con_red_declaran_la_barrera_central():
    for ruta in ARCHIVOS_CON_RED:
        fuente = Path(ruta).read_text(encoding="utf-8-sig")
        assert "seguridad_entorno" in fuente, ruta
        assert any(token in fuente for token in (
            "exigir_conexion_externa",
            "exigir_efecto_externo",
            "efectos_externos_habilitados",
            "conexiones_externas_habilitadas",
        )), ruta


def test_ipc_y_sentry_forman_parte_del_diagnostico_desconectado():
    fuente = Path("services/seguridad_entorno.py").read_text(encoding="utf-8-sig")
    assert '"IPC", "SENTRY"' in fuente
