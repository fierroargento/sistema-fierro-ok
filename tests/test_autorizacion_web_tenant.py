from pathlib import Path
from types import SimpleNamespace

import services.autorizacion_web as modulo


class GTemporal:
    pass


def preparar_contexto_web(
    monkeypatch,
    *,
    organizacion_id=None,
):
    contexto = GTemporal()
    sesion = {}

    if organizacion_id is not None:
        sesion["organizacion_id"] = (
            organizacion_id
        )

    monkeypatch.setattr(
        modulo,
        "g",
        contexto,
    )
    monkeypatch.setattr(
        modulo,
        "session",
        sesion,
    )

    return contexto, sesion


def test_adaptador_reutiliza_membresia_en_request(
    monkeypatch,
):
    _contexto, sesion = preparar_contexto_web(
        monkeypatch
    )

    usuario = SimpleNamespace(id=4)
    membresia = SimpleNamespace(
        organizacion_id=8,
        rol="carga",
    )
    llamadas = []

    def resolver(*args, **kwargs):
        llamadas.append((args, kwargs))
        return membresia

    monkeypatch.setattr(
        modulo,
        "resolver_tenant_usuario",
        resolver,
    )

    primera = modulo.membresia_actual_web(
        usuario,
        UsuarioOrganizacion=object(),
    )
    segunda = modulo.membresia_actual_web(
        usuario,
        UsuarioOrganizacion=object(),
    )

    assert primera is membresia
    assert segunda is membresia
    assert len(llamadas) == 1
    assert sesion["organizacion_id"] == 8


def test_cambio_de_tenant_invalida_cache(
    monkeypatch,
):
    _contexto, sesion = preparar_contexto_web(
        monkeypatch,
        organizacion_id=8,
    )

    usuario = SimpleNamespace(id=4)
    llamadas = []

    def resolver(
        usuario_actual,
        *,
        UsuarioOrganizacion,
        organizacion_id,
    ):
        llamadas.append(organizacion_id)
        return SimpleNamespace(
            organizacion_id=organizacion_id,
            rol="admin",
        )

    monkeypatch.setattr(
        modulo,
        "resolver_tenant_usuario",
        resolver,
    )

    modulo.membresia_actual_web(
        usuario,
        UsuarioOrganizacion=object(),
    )

    sesion["organizacion_id"] = 9

    resultado = modulo.membresia_actual_web(
        usuario,
        UsuarioOrganizacion=object(),
    )

    assert llamadas == [8, 9]
    assert resultado.organizacion_id == 9


def test_adaptador_no_usa_rol_global():
    contenido = Path(
        "services/autorizacion_web.py"
    ).read_text(encoding="utf-8")

    assert "usuario.rol" not in contenido
    assert "resolver_tenant_usuario(" in contenido


def test_rol_actual_usa_membresia():
    contenido = Path("app.py").read_text(
        encoding="utf-8"
    )

    inicio = contenido.index(
        "def membresia_actual():"
    )
    fin = contenido.index(
        "def es_dispositivo_movil():",
        inicio,
    )
    bloque = contenido[inicio:fin]

    assert "membresia_actual_web(" in bloque
    assert "return membresia.rol" in bloque
    assert "return usuario.rol" not in bloque


def test_login_required_exige_tenant():
    contenido = Path("app.py").read_text(
        encoding="utf-8"
    )

    inicio = contenido.index(
        "def login_required(fn):"
    )
    fin = contenido.index(
        "def registrar_auditoria(",
        inicio,
    )
    bloque = contenido[inicio:fin]

    assert "membresia_actual() is None" in bloque
    assert "organizacion activa" in bloque
