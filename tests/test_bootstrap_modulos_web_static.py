from pathlib import Path


def _leer(ruta):
    return Path(ruta).read_text(
        encoding="utf-8"
    )


def test_app_delega_registro_modular():
    app = _leer("app.py")

    assert (
        "registrar_modulos_web("
        in app
    )
    assert (
        "from services.bootstrap_modulos_web import ("
        in app
    )

    for referencia in (
        "crear_blueprint_usuarios",
        "registrar_rutas_auth",
        "crear_blueprint_estructura",
        "crear_blueprint_crm",
        "crear_blueprint_inventario",
        "crear_blueprint_facturacion",
    ):
        assert referencia not in app


def test_bootstrap_registra_todos_los_modulos():
    contenido = _leer(
        "services/bootstrap_modulos_web.py"
    )

    assert contenido.count(
        "app.register_blueprint("
    ) == 5
    assert "registrar_rutas_auth(" in contenido

    for referencia in (
        "crear_blueprint_usuarios",
        "crear_blueprint_estructura",
        "crear_blueprint_crm",
        "crear_blueprint_inventario",
        "crear_blueprint_facturacion",
    ):
        assert referencia in contenido


def test_dependencias_permanecen_explicitas():
    app = _leer("app.py")

    for dependencia in (
        '"db": db',
        '"limiter": limiter',
        '"login_required": login_required',
        '"usuario_actual": usuario_actual',
        '"membresia_actual": membresia_actual',
        '"registrar_auditoria": registrar_auditoria',
        '"UsuarioOrganizacion": UsuarioOrganizacion',
        '"UsuarioSistema": UsuarioSistema',
        '"Auditoria": Auditoria',
    ):
        assert dependencia in app

    assert "locals()" not in app
    assert "globals()" not in app
