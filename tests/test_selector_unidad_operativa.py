from pathlib import Path


def test_guardian_operativo_exige_organizacion_y_unidad():
    app = Path("app.py").read_text(encoding="utf-8-sig")
    consulta = app.split("def consulta_pedidos_tenant_actual():", 1)[1].split(
        "def pedido_tenant_actual_o_404", 1
    )[0]
    detalle = app.split("def pedido_tenant_actual_o_404(pedido_id):", 1)[1].split(
        "def rol_actual", 1
    )[0]
    assert "membresia.organizacion_id" in consulta
    assert "unidad = unidad_negocio_actual_o_403" in consulta
    assert "unidad_negocio_id=unidad.id" in consulta
    assert "membresia.organizacion_id" in detalle
    assert "unidad_negocio_id=unidad.id" in detalle


def test_selector_global_valida_pertenencia_y_actividad():
    app = Path("app.py").read_text(encoding="utf-8-sig")
    bloque = app.split("def seleccionar_unidad_operativa():", 1)[1].split(
        "\n@app.route", 1
    )[0]
    assert "organizacion_id=membresia.organizacion_id" in bloque
    assert "activa=True" in bloque
    assert "abort(404)" in bloque
    assert 'session["unidad_negocio_id"] = unidad.id' in bloque


def test_selector_se_muestra_en_layout_y_tiene_csrf_global():
    base = Path("templates/base.html").read_text(encoding="utf-8-sig")
    assert "unidades_operativas" in base
    assert "seleccionar_unidad_operativa" in base
    assert 'name="unidad_negocio_id"' in base
    assert "form[method=" in base


def test_legacy_sin_unidad_no_tiene_compatibilidad_operativa():
    servicio = Path("services/acceso_tenant_pedidos.py").read_text(
        encoding="utf-8-sig"
    )
    assert "unidad_negocio_id" in servicio
    assert "is_(None)" not in servicio
