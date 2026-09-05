from pathlib import Path


RUTAS_EXTERNAS = (
    "resync_ml_pedido",
    "sync_mensajes_ml_pedido_admin",
    "resync_tn_pedido",
    "actualizar_tracking_externo_pedido",
    "recalcular_correo_pedido",
    "actualizar_andreani_pedido",
    "eliminar_pedido",
    "marcar_contacto_ml",
    "desmarcar_contacto_ml",
    "enviar_mensaje_ml_acordas",
    "ia_analizar_respuesta_pedido",
    "ia_enviar_respuesta_faltantes_pedido",
    "whatsapp_enviar_operador",
    "whatsapp_iniciar_chat_operador",
    "whatsapp_tomar_conversacion",
    "whatsapp_reactivar_bot",
    "whatsapp_enviar_propuesta_cross_sell",
    "whatsapp_omitir_cross_sell",
    "confirmar_entrega",
    "confirmar_cierre_pedido",
    "devolver_pedido_a_ml",
    "avanzar_pedido",
)


def _app():
    return Path("app.py").read_text(encoding="utf-8")


def _funcion(nombre):
    return _app().split(f"def {nombre}(", 1)[1].split("\n@app.route", 1)[0]


def test_veintidos_rutas_externas_exigen_pedido_del_tenant():
    assert len(RUTAS_EXTERNAS) == 22
    for nombre in RUTAS_EXTERNAS:
        bloque = _funcion(nombre)
        assert "pedido_tenant_actual_o_404(id)" in bloque, nombre
        assert "Pedido.query.get_or_404(id)" not in bloque, nombre


def test_frontera_tenant_es_anterior_a_efectos_o_permisos():
    marcadores = (
        "rol_actual()", "puede_", "db.session.commit", "db.session.delete",
        "ml_api_contexto", "ml_sync", "tn_importar", "wa_enviar",
        "consultar_", "devolver_conversacion_a_ml(",
    )
    for nombre in RUTAS_EXTERNAS:
        bloque = _funcion(nombre)
        frontera = bloque.index("pedido_tenant_actual_o_404(id)")
        posiciones = [
            posicion for marcador in marcadores
            if (posicion := bloque.find(marcador)) >= 0
        ]
        assert posiciones and frontera < min(posiciones), nombre


def test_no_quedan_accesos_globales_por_id_en_rutas_de_pedido():
    app = _app()
    assert "Pedido.query.get_or_404(id)" not in app


def test_guardian_no_habilita_transporte_ni_escribe():
    app = _app()
    helper = app.split("def pedido_tenant_actual_o_404(", 1)[1].split(
        "def rol_actual(", 1
    )[0].lower()
    for prohibido in (
        "requests", "oauth", "webhook", "access_token", "db.session.commit",
        "db.session.add", "db.session.delete", "ml_sync", "tn_sync", "wa_enviar",
    ):
        assert prohibido not in helper


def test_no_se_agregan_credenciales_ni_configuracion_de_canales():
    servicio = Path("services/acceso_tenant_pedidos.py").read_text(encoding="utf-8")
    assert "organizacion_id" in servicio
    for prohibido in ("token", "secret", "client_id", "requests", "http"):
        assert prohibido not in servicio.lower()
