from pathlib import Path


def test_panel_expone_flujo_manual_completo():
    plantilla = Path("templates/admin_mercado_libre_offline.html").read_text(encoding="utf-8")
    for valor in ("preparar_tareas", "aprobar_tarea", "rechazar_tarea", "completar_tarea", "archivar_tarea", "exportar_tareas"):
        assert f'value="{valor}"' in plantilla
    assert "Ejecución automática: NO" in plantilla
    assert "Comprobante manual" in plantilla


def test_ruta_limita_lotes_y_tareas_al_tenant_activo():
    fuente = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    bloque = fuente.split("def mercado_libre_offline_comercial", 1)[1].split('@blueprint.route("/admin/comercial/preparacion-integraciones"', 1)[0]
    assert bloque.count("organizacion_id=organizacion.id") >= 6
    assert bloque.count("unidad_negocio_id=unidad_activa.id") >= 6
    assert "TareaML.query.get" not in bloque


def test_panel_no_habilita_ejecucion_automatica():
    ruta = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8").lower()
    bloque = ruta.split("def mercado_libre_offline_comercial", 1)[1].split('@blueprint.route("/admin/comercial/preparacion-integraciones"', 1)[0]
    for prohibido in ("requests.", "urlopen", "access_token", "client_secret", "mercadolibre.com"):
        assert prohibido not in bloque
    assert "puede_ejecutar=true" not in bloque.replace(" ", "")


def test_exportacion_es_descarga_y_no_ejecucion():
    fuente = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    bloque = fuente.split('if accion == "exportar_tareas":', 1)[1].split('if accion == "preparar_tareas":', 1)[0]
    assert "send_file" in bloque and "exportar_tareas" in bloque
    assert "db.session" not in bloque
