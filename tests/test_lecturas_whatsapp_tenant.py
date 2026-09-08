from pathlib import Path


def test_historial_del_pedido_filtra_tenant():
    app = Path("app.py").read_text(encoding="utf-8")
    bloque = app.split("whatsapp_mensajes = (", 1)[1].split(
        "message_ids_meta =", 1
    )[0]
    assert "pedido_id=pedido.id" in bloque
    assert "organizacion_id=pedido.organizacion_id" in bloque


def test_ventana_24_horas_exige_identidad_del_pedido():
    runtime = Path("modules/whatsapp/runtime.py").read_text(encoding="utf-8")
    bloque = runtime.split("def wa_ventana_24h_abierta_service(", 1)[1].split(
        "def wa_ventana_24h_abierta(", 1
    )[0]
    assert 'getattr(pedido, "organizacion_id", None)' in bloque
    assert "WhatsAppMensaje.organizacion_id == int(organizacion_id)" in bloque
    assert "if organizacion_id is None:" in bloque


def test_bandeja_general_usa_tenant_de_sesion():
    rutas = Path("modules/whatsapp/general_routes.py").read_text(encoding="utf-8")
    assert 'session.get("organizacion_id")' in rutas
    assert rutas.count("consulta_whatsapp_tenant(") == 3
    assert "organizacion_id=organizacion_id" in rutas


def test_servicio_general_particiona_mensajes_y_pedidos():
    servicio = Path("services/wa_general.py").read_text(encoding="utf-8")
    assert servicio.count("organizacion_id=int(organizacion_id)") >= 3
    assert "organizacion_id=organizacion_id" in servicio


def test_lote_no_modifica_webhook_ni_transporte():
    rutas = Path("modules/whatsapp/general_routes.py").read_text(encoding="utf-8")
    runtime = Path("modules/whatsapp/runtime.py").read_text(encoding="utf-8")
    assert "def registrar_whatsapp_mensaje_service(" in runtime
    assert '@app.route("/wa-general/enviar", methods=["POST"])' in rutas
    assert '@app.route("/wa-general/enviar-template-operador", methods=["POST"])' in rutas
