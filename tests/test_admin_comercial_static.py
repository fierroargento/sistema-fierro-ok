from pathlib import Path


def test_panel_comercial_es_modular_y_admin():
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    bootstrap = Path("services/bootstrap_modulos_web.py").read_text(encoding="utf-8")
    app = Path("app.py").read_text(encoding="utf-8")
    assert 'Blueprint("admin_comercial"' in rutas
    assert 'membresia.rol != "admin"' in rutas
    assert 'crear_blueprint_comercial' in bootstrap
    assert 'modules.admin.comercial.routes' not in app
    assert '/admin/comercial' not in app


def test_panel_no_publica_canales():
    archivos = [
        "modules/admin/comercial/routes.py",
        "services/comercial_admin.py",
        "services/comercial_consultas.py",
    ]
    contenido = "".join(Path(a).read_text(encoding="utf-8") for a in archivos)
    for texto in ("MercadoLibreCuenta", "TiendaNubeCuenta", "WebhookML"):
        assert texto not in contenido


def test_template_declara_que_no_sincroniza():
    template = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    assert "No publica ni sincroniza canales" in template
    assert 'value="crear_precio"' in template
    assert 'value="activar_precio"' in template
