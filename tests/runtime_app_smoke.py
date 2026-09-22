"""Smoke real: se ejecuta en un subproceso sin los dobles de tests/conftest.py."""

from werkzeug.security import check_password_hash

import app as modulo
from services.ajustes_costos_ipc import actualizar_indices_oficiales


aplicacion = modulo.app
db = modulo.db
aplicacion.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)

with aplicacion.app_context():
    db.create_all()
    organizacion = modulo.Organizacion(
        nombre="Fierro UAT",
        slug="fierro-uat",
        activa=True,
    )
    unidad = modulo.UnidadNegocio(
        organizacion=organizacion,
        nombre="Fierro",
        codigo="fierro",
        activa=True,
    )
    db.session.add_all([organizacion, unidad])
    db.session.commit()
    organizacion_id = organizacion.id
    unidad_id = unidad.id

runner = aplicacion.test_cli_runner()
resultado = runner.invoke(
    args=[
        "crear-admin-inicial",
        "--username", "admin-uat",
        "--nombre", "Administrador UAT",
        "--password", "Clave-UAT-Segura-2026",
        "--organizacion", "fierro-uat",
    ],
)
assert resultado.exit_code == 0, resultado.output

with aplicacion.app_context():
    usuario = modulo.UsuarioSistema.query.filter_by(username="admin-uat").one()
    membresia = modulo.UsuarioOrganizacion.query.filter_by(
        usuario_id=usuario.id,
        organizacion_id=organizacion_id,
    ).one()
    assert membresia.rol == "admin"
    assert check_password_hash(usuario.password_hash, "Clave-UAT-Segura-2026")
    ids = usuario.id, organizacion_id, unidad_id


def _red_no_debe_invocarse(*_args, **_kwargs):
    raise AssertionError("El modo laboratorio intentó abrir la red para IPC.")


with aplicacion.app_context():
    try:
        actualizar_indices_oficiales(
            desde=__import__("datetime").date(2026, 1, 1),
            hasta=__import__("datetime").date(2026, 2, 1),
            IndiceIPCOficial=modulo.IndiceIPCOficial,
            db_session=db.session,
            urlopen_fn=_red_no_debe_invocarse,
        )
    except RuntimeError as error:
        assert "bloqueada" in str(error)
    else:
        raise AssertionError("La consulta IPC no fue bloqueada.")

cliente = aplicacion.test_client()
with cliente.session_transaction() as sesion:
    sesion["user_id"] = ids[0]
    sesion["username"] = "admin-uat"
    sesion["organizacion_id"] = ids[1]
    sesion["unidad_negocio_id"] = ids[2]

revisadas = 0
for regla in sorted(aplicacion.url_map.iter_rules(), key=lambda item: item.rule):
    if (
        "GET" not in regla.methods
        or regla.arguments
        or regla.endpoint == "static"
        or regla.rule == "/logout"
    ):
        continue
    respuesta = cliente.get(
        regla.rule,
        base_url="https://localhost",
        follow_redirects=False,
    )
    assert respuesta.status_code < 500, (
        regla.rule,
        respuesta.status_code,
        respuesta.get_data(as_text=True)[:500],
    )
    revisadas += 1

assert revisadas >= 100, revisadas
print(f"RUNTIME_SMOKE_OK rutas={revisadas}")
