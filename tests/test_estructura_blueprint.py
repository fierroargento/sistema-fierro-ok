from pathlib import Path


def test_blueprint_declara_urls_y_endpoints():
    routes = Path(
        "modules/admin/estructura/routes.py"
    ).read_text(encoding="utf-8")

    assert (
        'Blueprint(\n'
        '        "admin_estructura",'
        in routes
    )
    assert (
        '@blueprint.route("/admin/estructura")'
        in routes
    )
    assert (
        '"/admin/estructura/guardar"'
        in routes
    )
    assert 'methods=["POST"]' in routes
    assert "def panel():" in routes
    assert "def guardar():" in routes
    assert (
        '"admin_estructura.panel"'
        in routes
    )
