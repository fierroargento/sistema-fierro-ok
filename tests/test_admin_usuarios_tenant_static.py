from pathlib import Path


def _leer(ruta):
    return Path(ruta).read_text(
        encoding="utf-8"
    )


def test_app_registra_blueprint_usuarios():
    contenido = _leer("app.py")

    assert (
        "crear_blueprint_usuarios"
        in contenido
    )
    assert (
        "app.register_blueprint("
        in contenido
    )


def test_app_no_conserva_rutas_monoliticas():
    contenido = _leer("app.py")

    assert (
        '@app.route("/admin/usuarios")'
        not in contenido
    )
    assert (
        "def admin_usuario_nuevo"
        not in contenido
    )
    assert (
        "def admin_usuario_editar"
        not in contenido
    )
    assert (
        "def admin_usuario_toggle"
        not in contenido
    )
    assert "ROLES_SISTEMA" not in contenido


def test_blueprint_conserva_urls():
    contenido = _leer(
        "modules/admin/usuarios/routes.py"
    )

    assert (
        '@blueprint.route("/admin/usuarios")'
        in contenido
    )
    assert (
        '"/admin/usuarios/nuevo"'
        in contenido
    )
    assert (
        '"/admin/usuarios/<int:id>/editar"'
        in contenido
    )
    assert (
        '"/admin/usuarios/<int:id>/toggle"'
        in contenido
    )


def test_blueprint_autoriza_por_membresia():
    contenido = _leer(
        "modules/admin/usuarios/routes.py"
    )

    assert (
        "resolver_tenant_usuario("
        in contenido
    )
    assert 'membresia.rol != "admin"' in contenido
    assert (
        'session["organizacion_id"]'
        in contenido
    )


def test_consulta_filtra_organizacion():
    contenido = _leer(
        "services/usuarios_consultas.py"
    )

    assert (
        "UsuarioOrganizacion.organizacion_id"
        in contenido
    )
    assert "== organizacion_id" in contenido


def test_mutaciones_resuelven_membresia_tenant():
    contenido = _leer(
        "services/usuarios_admin.py"
    )

    assert (
        "organizacion_id=organizacion.id"
        in contenido
    )
    assert (
        contenido.count(
            "_membresia_tenant("
        )
        >= 3
    )


def test_estado_modifica_membresia():
    contenido = _leer(
        "services/usuarios_admin.py"
    )

    assert (
        "membresia.activa = not bool("
        in contenido
    )
    assert (
        "No podés desactivar tu propia"
        in contenido
    )


def test_identidad_global_no_se_reutiliza():
    contenido = _leer(
        "services/usuarios_admin.py"
    )

    assert (
        "Ese usuario ya existe"
        in contenido
    )
    assert (
        "invitación segura"
        in contenido
    )


def test_template_usa_membresias():
    contenido = _leer(
        "templates/admin_usuarios.html"
    )

    assert (
        "for membresia in membresias"
        in contenido
    )
    assert "membresia.rol" in contenido
    assert "membresia.activa" in contenido
    assert (
        "admin_usuarios.nuevo"
        in contenido
    )
    assert (
        "admin_usuarios.editar"
        in contenido
    )
    assert (
        "admin_usuarios.toggle"
        in contenido
    )
