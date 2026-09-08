import json
from pathlib import Path

from services.certificacion_offline_whatsapp import certificar_escenarios_whatsapp
from services.modo_sombra_whatsapp import (
    BLOQUEOS_SOMBRA, evaluar_lote_en_sombra, evaluar_payload_en_sombra,
    exportar_evidencia_sombra, matriz_preparacion_sombra,
)


VINCULO = {"whatsapp_phone_number_id": "P1", "organizacion_id": 2, "unidad_negocio_id": 3, "estado": "activo"}


def payload(identificador="m1"):
    return {"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "P1"}, "messages": [{"id": identificador, "from": "549", "type": "text", "text": {"body": "Hola"}}]}}]}]}


def test_sombra_proyecta_pero_no_ejecuta():
    resultado = evaluar_payload_en_sombra(payload(), [VINCULO])
    assert resultado["decisiones"][0]["ejecutada"] is False
    assert resultado["aplicable"] is False
    assert all(valor is False for valor in resultado["bloqueos"].values())


def test_compara_con_observacion_legado():
    observado = [{"referencia": "m1:in", "organizacion_id": 2, "unidad_negocio_id": 3, "accion_proyectada": "evaluar_enrutamiento_sin_ejecutar"}]
    assert evaluar_payload_en_sombra(payload(), [VINCULO], legado_observado=observado)["diferencias"] == []


def test_lote_deduplica_entre_documentos():
    resultado = evaluar_lote_en_sombra([payload(), payload(), payload("m2")], [VINCULO])
    assert resultado["resumen"]["documentos"] == 3
    assert resultado["resumen"]["eventos"] == 2
    assert resultado["acciones_externas"] == resultado["escrituras"] == 0


def test_matriz_nunca_habilita_conexion():
    matriz = matriz_preparacion_sombra([VINCULO], certificar_escenarios_whatsapp())
    assert matriz["apta_para_ensayo_manual"] is True
    assert matriz["apta_para_conexion"] is False


def test_evidencia_es_determinista_y_exportable():
    resultado = evaluar_payload_en_sombra(payload(), [VINCULO])
    repetido = evaluar_payload_en_sombra(payload(), [VINCULO])
    assert resultado["firma_evidencia"] == repetido["firma_evidencia"]
    exportado = json.loads(exportar_evidencia_sombra(resultado).getvalue().decode("utf-8"))
    assert exportado["modo"] == "sombra_desconectada"


def test_panel_tenant_y_webhook_fuera_del_bloque():
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_sombra_whatsapp.html").read_text(encoding="utf-8")
    assert "/admin/comercial/whatsapp-sombra" in rutas
    assert "SOMBRA DESCONECTADA" in panel
    assert "organizacion_id=organizacion.id" in rutas
    assert "unidad_negocio_id=unidad_activa.id" in rutas
    webhook = Path("modules/whatsapp/webhook.py").read_text(encoding="utf-8")
    assert "modo_sombra_whatsapp" not in webhook


def test_servicio_no_tiene_transporte_persistencia_ni_credenciales():
    fuente = Path("services/modo_sombra_whatsapp.py").read_text(encoding="utf-8").lower()
    for prohibido in ("requests", "urlopen", "db.session", "commit(", "access_token", "app_secret", "http://", "https://"):
        assert prohibido not in fuente
