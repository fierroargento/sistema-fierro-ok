import json
from pathlib import Path

from services.procesador_offline_whatsapp import exportar_diagnostico_whatsapp_offline


def test_exportacion_json_es_utf8_y_operable():
    resultado = {
        "sobres": [{"texto": "Información"}], "duplicados": [],
        "errores": [], "resumen": {"procesados": 1},
        "escrituras": 0, "acciones_externas": 0,
    }
    datos = json.loads(
        exportar_diagnostico_whatsapp_offline(resultado).getvalue().decode("utf-8")
    )
    assert datos["sobres"][0]["texto"] == "Información"
    assert datos["acciones_externas"] == 0


def test_bandeja_existe_y_declara_bloqueos():
    plantilla = Path("templates/admin_whatsapp_offline.html").read_text(encoding="utf-8")
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    assert "/admin/comercial/whatsapp-offline" in rutas
    assert "organizacion_id=organizacion.id" in rutas
    assert "unidad_negocio_id=unidad_activa.id" in rutas
    assert "0 acciones externas · 0 escrituras" in plantilla
    assert "Exportar diagnóstico JSON" in plantilla


def test_ruta_no_registra_staging_ni_modifica_webhook():
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    bloque = rutas.split("def whatsapp_offline_comercial", 1)[1].split(
        '@blueprint.route("/admin/comercial/preparacion-integraciones"', 1
    )[0]
    assert "registrar_evento(" not in bloque
    assert "db.session" not in bloque
    webhook = Path("modules/whatsapp/webhook.py").read_text(encoding="utf-8")
    assert "procesador_offline_whatsapp" not in webhook
