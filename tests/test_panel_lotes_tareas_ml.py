from pathlib import Path


def fuentes():
    return (Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8"), Path("templates/admin_mercado_libre_offline.html").read_text(encoding="utf-8"))


def test_panel_exige_previsualizacion_antes_de_confirmar():
    ruta, html = fuentes()
    assert 'accion" value="previsualizar_lote_tareas"' in html
    assert 'accion" value="aplicar_lote_tareas"' in html
    assert "vista_lote.puede_aplicar" in html
    assert "previsualizar_lote(" in ruta and "aplicar_lote(" in ruta


def test_seleccion_y_consultas_respetan_tenant():
    ruta, html = fuentes()
    bloque = ruta.split('if accion in {"previsualizar_lote_tareas", "aplicar_lote_tareas"}:',1)[1].split('if accion == "exportar_tareas":',1)[0]
    assert "TareaML.id.in_(ids)" in bloque
    assert bloque.count("organizacion_id=organizacion.id") >= 3
    assert bloque.count("unidad_negocio_id=unidad_activa.id") >= 3
    assert 'type="checkbox" name="tarea_ids"' in html


def test_exporta_evidencia_sin_mutacion():
    ruta, html = fuentes()
    bloque = ruta.split('if accion == "exportar_evidencia_tareas":',1)[1].split('if accion in {"previsualizar_lote_tareas"',1)[0]
    assert "exportar_evidencia" in bloque and "send_file" in bloque
    assert "db.session" not in bloque
    assert "exportar_evidencia_tareas" in html


def test_ruta_no_contiene_transporte_mercado_libre():
    ruta, _ = fuentes()
    bloque = ruta.lower().split("def mercado_libre_offline_comercial",1)[1].split('@blueprint.route("/admin/comercial/preparacion-integraciones"',1)[0]
    assert not any(x in bloque for x in ("requests.", "urlopen", "access_token", "client_secret"))
    assert "puede_ejecutar=true" not in bloque.replace(" ", "")
