from pathlib import Path
import subprocess
import sys


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


def test_panel_administra_catalogos_sin_app_py():
    template = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    servicio = Path("services/catalogos_admin_comercial.py").read_text(
        encoding="utf-8"
    )
    app = Path("app.py").read_text(encoding="utf-8")

    for accion in (
        "crear_catalogo",
        "estado_catalogo",
        "agregar_producto_catalogo",
        "activar_producto_catalogo",
        "disponibilidad_producto_catalogo",
    ):
        assert accion in template
    assert "procesar_accion_catalogo_comercial" in servicio
    assert "/admin/comercial" not in app


def test_selector_del_maestro_permite_buscar_sin_dependencias():
    template = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    javascript = Path("static/admin_comercial.js").read_text(encoding="utf-8")

    assert 'id="buscar-producto-maestro"' in template
    assert 'id="producto-maestro"' in template
    assert "admin_comercial.js" in template
    assert 'getElementById("buscar-producto-maestro")' in javascript
    assert "productos.filter" in javascript
    assert "slice(0, limite)" in javascript


def test_catalogos_comerciales_no_conectan_consumidores_productivos():
    contenidos = "\n".join(
        Path(ruta).read_text(encoding="utf-8")
        for ruta in (
            "services/catalogos_admin_comercial.py",
            "services/comercial_admin.py",
            "services/comercial_consultas.py",
        )
    )
    for prohibido in (
        "Pedido.query",
        "ml_sync",
        "tn_sync",
        "facturar_pedido",
        "ml_upsert_pedido",
        "tn_importar_o_actualizar_pedido",
    ):
        assert prohibido not in contenidos


def test_panel_bloquea_etapas_sin_prerrequisitos():
    template = Path("templates/admin_comercial.html").read_text(encoding="utf-8")

    assert "inclusiones_activas" in template
    assert "hay_costos_vigentes" in template
    assert "hay_politicas_vigentes" in template
    assert template.count("prerequisite-warning") >= 4


def test_runtime_catalogos_comerciales_sqlite():
    resultado = subprocess.run(
        [sys.executable, "scripts/verificar_catalogos_comerciales_runtime.py"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert "Runtime SQLite de catalogos comerciales OK" in resultado.stdout
