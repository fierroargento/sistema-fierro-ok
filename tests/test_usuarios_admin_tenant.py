from types import SimpleNamespace

import pytest

from services.usuarios_admin import (
    _membresia_tenant,
)


class QueryFalsa:
    def __init__(self, resultado):
        self.resultado = resultado
        self.filtros = None

    def filter_by(self, **filtros):
        self.filtros = filtros
        return self

    def first(self):
        if self.resultado is None:
            return None

        if (
            self.resultado.id
            != self.filtros["id"]
            or self.resultado.organizacion_id
            != self.filtros["organizacion_id"]
        ):
            return None

        return self.resultado


def test_membresia_pertenece_al_tenant():
    membresia = SimpleNamespace(
        id=7,
        organizacion_id=10,
    )
    modelo = SimpleNamespace(
        query=QueryFalsa(membresia)
    )

    resultado = _membresia_tenant(
        7,
        organizacion=SimpleNamespace(id=10),
        UsuarioOrganizacion=modelo,
    )

    assert resultado is membresia


def test_rechaza_membresia_de_otro_tenant():
    membresia = SimpleNamespace(
        id=7,
        organizacion_id=20,
    )
    modelo = SimpleNamespace(
        query=QueryFalsa(membresia)
    )

    with pytest.raises(
        ValueError,
        match="organización activa",
    ):
        _membresia_tenant(
            7,
            organizacion=SimpleNamespace(id=10),
            UsuarioOrganizacion=modelo,
        )


def test_rechaza_id_invalido():
    modelo = SimpleNamespace(
        query=QueryFalsa(None)
    )

    with pytest.raises(
        ValueError,
        match="no es válida",
    ):
        _membresia_tenant(
            "incorrecto",
            organizacion=SimpleNamespace(id=10),
            UsuarioOrganizacion=modelo,
        )
