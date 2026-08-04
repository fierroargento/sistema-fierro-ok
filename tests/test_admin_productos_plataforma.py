from types import SimpleNamespace
from pathlib import Path

from modules.admin.productos.routes import (
    _es_organizacion_plataforma,
)


def test_solo_organizacion_inicial_es_plataforma():
    assert _es_organizacion_plataforma(
        SimpleNamespace(slug="grupo-fierro")
    )
    assert not _es_organizacion_plataforma(
        SimpleNamespace(slug="otro-tenant")
    )
    assert not _es_organizacion_plataforma(
        SimpleNamespace()
    )


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


def test_maestro_global_no_se_presenta_como_tenant():
    rutas = Path(
        "modules/admin/productos/routes.py"
    ).read_text(encoding="utf-8")
    consultas = Path(
        "services/productos_consultas.py"
    ).read_text(encoding="utf-8")

    assert (
        "SLUG_ORGANIZACION_PLATAFORMA"
        in rutas
    )
    assert "CatalogoProducto" not in consultas
    assert "organizacion_id" not in consultas


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
