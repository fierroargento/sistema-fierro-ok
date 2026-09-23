from pathlib import Path
from types import SimpleNamespace

from modules.whatsapp import webhook


def test_webhook_resuelve_tenant_antes_de_procesar_eventos():
    fuente = Path("modules/whatsapp/webhook.py").read_text(encoding="utf-8-sig")
    inicio = fuente.index("def webhook_whatsapp():")
    bloque = fuente[inicio:]
    resolver = bloque.index("resolver_configuracion_post_whatsapp(")
    firma = bloque.index("validar_signature_meta(")
    estados = bloque.index("_procesar_statuses_whatsapp(statuses, organizacion_id)")
    mensajes = bloque.index("for msg in messages:")
    assert resolver < firma < estados < mensajes
    assert '"status": "forbidden"' in bloque


def test_webhook_tenantiza_deduplicacion_busqueda_historial_y_media():
    fuente = Path("modules/whatsapp/webhook.py").read_text(encoding="utf-8-sig")
    for contrato in (
        "organizacion_id=organizacion_id",
        "_buscar_pedido_por_telefono(telefono, organizacion_id)",
        "unidad_negocio_id=unidad_negocio_id",
        "organizacion_id=organizacion_id,",
    ):
        assert contrato in fuente
    assert "pedido.unidad_negocio_id" in fuente


def test_salida_general_recibe_contexto_organizacion_aunque_sigue_bloqueada():
    bot = Path("services/wa_general_bot.py").read_text(encoding="utf-8-sig")
    router = Path("modules/whatsapp/router.py").read_text(encoding="utf-8-sig")
    assert "organizacion_id" in bot
    assert "organizacion_id=organizacion_id" in router


def test_webhook_no_depende_de_secretos_globales_legacy():
    fuente = Path("modules/whatsapp/webhook.py").read_text(encoding="utf-8-sig")
    inicio = Path("modules/whatsapp/__init__.py").read_text(encoding="utf-8-sig")
    assert "WA_VERIFY_TOKEN" not in fuente
    assert "WA_APP_SECRET" not in fuente
    assert "modulo_activo" not in fuente
    assert "modulo_activo" not in inicio
    assert "registrar_webhook(app)" in inicio


def test_ruta_registrada_en_uat_corta_antes_de_base_y_credenciales(monkeypatch):
    llamados = []

    class AppFake:
        def __init__(self):
            self.vista = None

        def route(self, *_args, **_kwargs):
            def registrar(funcion):
                self.vista = funcion
                return funcion
            return registrar

    monkeypatch.setattr(
        webhook, "procesamiento_webhook_habilitado", lambda _canal: False,
    )
    monkeypatch.setattr(
        webhook, "resolver_configuracion_post_whatsapp",
        lambda *_args, **_kwargs: llamados.append("post"),
    )
    monkeypatch.setattr(
        webhook, "resolver_configuracion_verificacion_whatsapp",
        lambda *_args, **_kwargs: llamados.append("get"),
    )
    monkeypatch.setattr(webhook, "jsonify", lambda contenido: contenido)
    solicitud = SimpleNamespace(method="GET")
    monkeypatch.setattr(webhook, "request", solicitud)
    app = AppFake()
    webhook.registrar_webhook(app)

    respuesta_get = app.vista()
    solicitud.method = "POST"
    respuesta_post = app.vista()

    assert respuesta_get == ({"status": "ignored", "reason": "disconnected"}, 200)
    assert respuesta_post == ({"status": "ignored", "reason": "disconnected"}, 200)
    assert llamados == []


def test_media_no_usa_empresa_global_fija():
    fuente = Path("modules/whatsapp/media_inbound.py").read_text(encoding="utf-8-sig")
    assert "empresa_id=int(organizacion_id)" in fuente
    assert "empresa_id=1" not in fuente
