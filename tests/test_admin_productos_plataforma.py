from pathlib import Path


def test_ruta_monolitica_fue_eliminada():
    contenido = Path(
        "app.py"
    ).read_text(encoding="utf-8")

    assert "def admin_productos(" not in contenido
    assert (
        '@app.route("/admin/productos"'
        not in contenido
    )
    assert (
        "crear_blueprint_productos("
        in contenido
    )


def test_registro_inyecta_usuario_actual_real():
    contenido = Path(
        "app.py"
    ).read_text(encoding="utf-8")

    assert (
        '"usuario_actual": usuario_actual'
        in contenido
    )
    assert "lambda: current_user" not in contenido


def test_blueprint_conserva_url():
    contenido = Path(
        "modules/admin/productos/routes.py"
    ).read_text(encoding="utf-8")

    assert '"/admin/productos"' in contenido
    assert 'methods=["GET", "POST"]' in contenido
    assert "Blueprint(" in contenido
    assert (
        '"admin_productos"'
        in contenido
    )


def test_maestro_se_filtra_y_administra_por_tenant():
    rutas = Path(
        "modules/admin/productos/routes.py"
    ).read_text(encoding="utf-8")
    consultas = Path(
        "services/productos_consultas.py"
    ).read_text(encoding="utf-8")

    assert (
        "organizacion_id=("
        in rutas
    )
    assert "CatalogoProducto" not in consultas
    assert "organizacion_id" in consultas


def test_template_usa_endpoint_blueprint():
    plantilla = Path(
        "templates/admin_productos.html"
    ).read_text(encoding="utf-8")
    base = Path(
        "templates/base.html"
    ).read_text(encoding="utf-8")

    assert (
        "admin_productos.panel"
        in plantilla
    )
    assert "admin_productos.panel" in base
