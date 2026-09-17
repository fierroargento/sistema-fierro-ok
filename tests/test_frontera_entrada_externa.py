from pathlib import Path

from services.seguridad_entorno import diagnostico_laboratorio_desconectado


def _bloque(fuente, inicio, fin):
    return fuente.split(inicio, 1)[1].split(fin, 1)[0]


def test_diagnostico_incluye_puertas_no_api(monkeypatch):
    monkeypatch.delenv("SISTEMA_FIERRO_ENTORNO", raising=False)
    monkeypatch.delenv("CONEXIONES_EXTERNAS_HABILITADAS", raising=False)
    resultado = diagnostico_laboratorio_desconectado()
    assert resultado["desconectado"] is True
    assert resultado["canales"]["GEOCODING"]["conexion"] is False
    assert resultado["canales"]["DESCARGAS"]["conexion"] is False


def test_oauth_ml_se_cierra_antes_de_redireccionar_o_intercambiar_token():
    fuente = Path("app.py").read_text(encoding="utf-8-sig")
    conectar = _bloque(fuente, "def conectar_mercadolibre():", '@app.route("/admin/integraciones/mercadolibre/callback")')
    callback = _bloque(fuente, "def callback_mercadolibre():", "def desconectar_mercadolibre(cuenta_id):")
    assert conectar.index('conexiones_externas_habilitadas("ML")') < conectar.index("https://auth.mercadolibre.com.ar/")
    assert callback.index('conexiones_externas_habilitadas("ML")') < callback.index("ml_exchange_code_for_token")


def test_webhook_whatsapp_ignora_antes_de_leer_y_escribir():
    fuente = Path("modules/whatsapp/webhook.py").read_text(encoding="utf-8-sig")
    bloque = _bloque(fuente, "def webhook_whatsapp():", "# ── Verificación inicial de Meta")
    assert 'procesamiento_webhook_habilitado("WHATSAPP")' in bloque
    assert '"status": "ignored"' in bloque


def test_descarga_y_geocodificacion_fallan_cerrado():
    fuente = Path("app.py").read_text(encoding="utf-8-sig")
    descarga = _bloque(fuente, "def asegurar_pdf_local_desde_url", "def _recortar_preview_pdf")
    geocoding = _bloque(fuente, "def nominatim(q):", "# 1) Nominatim")
    assert 'exigir_conexion_externa("DESCARGAS"' in descarga
    assert descarga.index('exigir_conexion_externa("DESCARGAS"') < descarga.index("urlopen(url_pdf)")
    assert 'exigir_conexion_externa("GEOCODING"' in geocoding
    assert geocoding.index('exigir_conexion_externa("GEOCODING"') < geocoding.index("urllib.request.urlopen")


def test_panel_expone_estado_del_laboratorio():
    rutas = Path("modules/admin/integraciones/routes.py").read_text(encoding="utf-8-sig")
    plantilla = Path("templates/admin_integraciones.html").read_text(encoding="utf-8-sig")
    assert "diagnostico_laboratorio_desconectado()" in rutas
    assert 'data-control="laboratorio-desconectado"' in plantilla
    assert "Las credenciales guardadas no abren conexiones" in plantilla
