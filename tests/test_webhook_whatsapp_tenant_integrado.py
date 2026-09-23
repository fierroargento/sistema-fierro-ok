from pathlib import Path


def test_webhook_resuelve_tenant_antes_de_procesar_eventos():
    fuente = Path("modules/whatsapp/webhook.py").read_text(encoding="utf-8-sig")
    inicio = fuente.index("def webhook_whatsapp():")
    bloque = fuente[inicio:]
    resolver = bloque.index("resolver_contexto_webhook_whatsapp(data, vinculos)")
    estados = bloque.index("_procesar_statuses_whatsapp(statuses, organizacion_id)")
    mensajes = bloque.index("for msg in messages:")
    assert resolver < estados < mensajes
    assert '"reason": "tenant_context"' in bloque


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


def test_media_no_usa_empresa_global_fija():
    fuente = Path("modules/whatsapp/media_inbound.py").read_text(encoding="utf-8-sig")
    assert "empresa_id=int(organizacion_id)" in fuente
    assert "empresa_id=1" not in fuente
