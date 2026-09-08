import json
from pathlib import Path

from services.certificacion_offline_whatsapp import (
    certificar_escenarios_whatsapp,
    exportar_certificacion_whatsapp,
)


def test_seis_escenarios_criticos_aprueban():
    resultado = certificar_escenarios_whatsapp()
    assert resultado["aprobada"] is True
    assert resultado["total"] == resultado["aprobados"] == 6
    assert resultado["rechazados"] == 0


def test_cubre_fronteras_obligatorias():
    codigos = {
        item["codigo"] for item in certificar_escenarios_whatsapp()["resultados"]
    }
    assert codigos == {
        "tenant_valido", "cuenta_desconocida", "tenant_ambiguo",
        "mensaje_duplicado", "estados_desordenados", "payload_invalido",
    }


def test_resultado_declara_cero_efectos():
    resultado = certificar_escenarios_whatsapp()
    assert resultado["escrituras"] == 0
    assert resultado["acciones_externas"] == 0


def test_exportacion_json_preserva_evidencia():
    resultado = certificar_escenarios_whatsapp()
    exportado = json.loads(
        exportar_certificacion_whatsapp(resultado).getvalue().decode("utf-8")
    )
    assert exportado["aprobada"] is True
    assert len(exportado["resultados"]) == 6


def test_panel_y_ruta_son_solo_lectura():
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    plantilla = Path("templates/admin_certificacion_whatsapp_offline.html").read_text(encoding="utf-8")
    bloque = rutas.split("def certificar_whatsapp_offline_comercial", 1)[1].split(
        '@blueprint.route("/admin/comercial/preparacion-integraciones"', 1
    )[0]
    assert "db.session" not in bloque
    assert "CERTIFICACIÓN APROBADA" in plantilla
    assert "0 escrituras · 0 acciones externas" in plantilla
    webhook = Path("modules/whatsapp/webhook.py").read_text(encoding="utf-8")
    assert "certificacion_offline_whatsapp" not in webhook
