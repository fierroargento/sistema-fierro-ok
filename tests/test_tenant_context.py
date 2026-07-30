from types import SimpleNamespace

import pytest

from services.tenant_context import (
    TenantAmbiguo,
    TenantNoAutorizado,
    asegurar_membresias_organizacion_inicial,
    seleccionar_membresia_tenant,
)


def membresia(
    organizacion_id,
    *,
    activa=True,
    organizacion_activa=True,
    predeterminada=False,
):
    return SimpleNamespace(
        organizacion_id=organizacion_id,
        activa=activa,
        predeterminada=predeterminada,
        organizacion=SimpleNamespace(
            activa=organizacion_activa,
        ),
    )


def test_selecciona_unico_tenant_activo():
    actual = membresia(10)

    assert (
        seleccionar_membresia_tenant([actual])
        is actual
    )


def test_seleccion_expresa_no_permite_otro_tenant():
    with pytest.raises(TenantNoAutorizado):
        seleccionar_membresia_tenant(
            [membresia(10)],
            organizacion_id=20,
        )


def test_selecciona_tenant_solicitado_autorizado():
    primera = membresia(10)
    segunda = membresia(20)

    assert (
        seleccionar_membresia_tenant(
            [primera, segunda],
            organizacion_id="20",
        )
        is segunda
    )


def test_varios_tenants_exigen_eleccion_segura():
    with pytest.raises(TenantAmbiguo):
        seleccionar_membresia_tenant([
            membresia(10),
            membresia(20),
        ])


def test_usa_unica_membresia_predeterminada():
    primera = membresia(10)
    segunda = membresia(
        20,
        predeterminada=True,
    )

    assert (
        seleccionar_membresia_tenant([
            primera,
            segunda,
        ])
        is segunda
    )


def test_ignora_membresias_u_organizaciones_inactivas():
    operativa = membresia(30)

    assert (
        seleccionar_membresia_tenant([
            membresia(10, activa=False),
            membresia(
                20,
                organizacion_activa=False,
            ),
            operativa,
        ])
        is operativa
    )


class MembresiaFake:
    def __init__(self, **datos):
        self.__dict__.update(datos)


class SessionFake:
    def __init__(self):
        self.agregados = []
        self.commits = 0

    def add(self, objeto):
        self.agregados.append(objeto)

    def commit(self):
        self.commits += 1


def test_backfill_crea_membresias_sin_activar_modulos():
    usuarios = [
        SimpleNamespace(
            id=1,
            rol="admin",
            activo=True,
        ),
        SimpleNamespace(
            id=2,
            rol="carga",
            activo=True,
        ),
    ]
    session = SessionFake()

    creadas = (
        asegurar_membresias_organizacion_inicial(
            UsuarioSistema=SimpleNamespace,
            UsuarioOrganizacion=MembresiaFake,
            organizacion_id=7,
            db_session=session,
            usuarios=usuarios,
            buscar_membresia_fn=(
                lambda _usuario_id, _org_id: None
            ),
            logger_fn=None,
        )
    )

    assert creadas == 2
    assert session.commits == 1
    assert len(session.agregados) == 2
    assert {
        objeto.usuario_id
        for objeto in session.agregados
    } == {1, 2}
    assert all(
        objeto.organizacion_id == 7
        for objeto in session.agregados
    )
    assert all(
        objeto.predeterminada is True
        for objeto in session.agregados
    )


def test_backfill_es_idempotente():
    session = SessionFake()
    usuarios = [
        SimpleNamespace(
            id=1,
            rol="admin",
            activo=True,
        ),
    ]

    creadas = (
        asegurar_membresias_organizacion_inicial(
            UsuarioSistema=SimpleNamespace,
            UsuarioOrganizacion=MembresiaFake,
            organizacion_id=7,
            db_session=session,
            usuarios=usuarios,
            buscar_membresia_fn=(
                lambda _usuario_id, _org_id: object()
            ),
            logger_fn=None,
        )
    )

    assert creadas == 0
    assert session.agregados == []
    assert session.commits == 0


def test_servicio_tenant_no_depende_de_flask():
    from pathlib import Path

    fuente = Path(
        "services/tenant_context.py"
    ).read_text(encoding="utf-8")

    assert "from flask" not in fuente
    assert "import flask" not in fuente
    assert "session[" not in fuente
    assert "request." not in fuente
