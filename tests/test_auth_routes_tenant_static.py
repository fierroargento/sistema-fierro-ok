from pathlib import Path


def test_auth_conserva_urls_y_endpoints():
    contenido = Path(
        "modules/auth/routes.py"
    ).read_text(encoding="utf-8")

    assert '"/login"' in contenido
    assert '@app.route("/logout")' in contenido
    assert "def login():" in contenido
    assert "def logout():" in contenido


def test_login_exige_membresia_activa():
    contenido = Path(
        "modules/auth/routes.py"
    ).read_text(encoding="utf-8")

    assert contenido.count(
        "membresia_actual()"
    ) == 2
    assert "session.clear()" in contenido
    assert "organizacion activa" in contenido


def test_login_no_autoriza_por_rol_global():
    contenido = Path(
        "modules/auth/routes.py"
    ).read_text(encoding="utf-8")

    assert "usuario.rol" not in contenido
    assert "rol_actual" not in contenido


def test_app_no_conserva_rutas_auth():
    contenido = Path("app.py").read_text(
        encoding="utf-8"
    )

    assert (
        '@app.route("/login"'
        not in contenido
    )
    assert (
        '@app.route("/logout")'
        not in contenido
    )
    assert (
        "registrar_rutas_auth("
        in contenido
    )
