from pathlib import Path
from types import SimpleNamespace

import pytest

from services.integraciones_tenant import (
    cuentas_mercado_libre_tenant,
    cuentas_tienda_nube_tenant,
    exigir_vinculo_cuenta_tenant,
    obtener_vinculos_canal_tenant,
)


class ConsultaFalsa:
    def __init__(
        self,
        registros,
        filtros=None,
    ):
        self.registros = list(registros)
        self.filtros = dict(filtros or {})

    def filter_by(self, **filtros):
        nuevos = dict(self.filtros)
        nuevos.update(filtros)

        return ConsultaFalsa(
            self.registros,
            nuevos,
        )

    def _resultados(self):
        return [
            registro
            for registro in self.registros
            if all(
                getattr(
                    registro,
                    campo,
                    None,
                )
                == valor
                for campo, valor
                in self.filtros.items()
            )
        ]

    def all(self):
        return self._resultados()

    def first(self):
        resultados = self._resultados()

        return (
            resultados[0]
            if resultados
            else None
        )


def modelo_vinculo(registros):
    return SimpleNamespace(
        query=ConsultaFalsa(registros)
    )


def crear_datos():
    cuenta_ml_a = SimpleNamespace(id=101)
    cuenta_ml_b = SimpleNamespace(id=102)
    cuenta_tn = SimpleNamespace(id=201)

    vinculos = [
        SimpleNamespace(
            organizacion_id=1,
            canal="mercadolibre",
            estado="activo",
            mercado_libre_cuenta_id=101,
            tienda_nube_cuenta_id=None,
            mercado_libre_cuenta=cuenta_ml_a,
            tienda_nube_cuenta=None,
        ),
        SimpleNamespace(
            organizacion_id=2,
            canal="mercadolibre",
            estado="activo",
            mercado_libre_cuenta_id=102,
            tienda_nube_cuenta_id=None,
            mercado_libre_cuenta=cuenta_ml_b,
            tienda_nube_cuenta=None,
        ),
        SimpleNamespace(
            organizacion_id=1,
            canal="tiendanube",
            estado="desactivado",
            mercado_libre_cuenta_id=None,
            tienda_nube_cuenta_id=201,
            mercado_libre_cuenta=None,
            tienda_nube_cuenta=cuenta_tn,
        ),
    ]

    return (
        vinculos,
        cuenta_ml_a,
        cuenta_ml_b,
        cuenta_tn,
    )


def test_lista_solamente_vinculos_del_tenant():
    vinculos, *_ = crear_datos()

    resultado = obtener_vinculos_canal_tenant(
        SimpleNamespace(id=1),
        VinculoCanalComercial=(
            modelo_vinculo(vinculos)
        ),
    )

    assert len(resultado) == 2
    assert {
        vinculo.organizacion_id
        for vinculo in resultado
    } == {1}


def test_resuelve_cuentas_por_tenant_y_canal():
    (
        vinculos,
        cuenta_ml_a,
        _cuenta_ml_b,
        cuenta_tn,
    ) = crear_datos()

    modelo = modelo_vinculo(vinculos)

    assert cuentas_mercado_libre_tenant(
        1,
        VinculoCanalComercial=modelo,
    ) == [cuenta_ml_a]

    assert cuentas_tienda_nube_tenant(
        1,
        VinculoCanalComercial=modelo,
    ) == [cuenta_tn]


def test_solo_activas_excluye_vinculo_desactivado():
    vinculos, *_ = crear_datos()

    assert cuentas_tienda_nube_tenant(
        1,
        VinculoCanalComercial=(
            modelo_vinculo(vinculos)
        ),
        solo_activas=True,
    ) == []


def test_rechaza_cuenta_de_otro_tenant():
    (
        vinculos,
        _cuenta_ml_a,
        cuenta_ml_b,
        _cuenta_tn,
    ) = crear_datos()

    with pytest.raises(
        ValueError,
        match="no pertenece",
    ):
        exigir_vinculo_cuenta_tenant(
            1,
            cuenta_ml_b,
            canal="mercadolibre",
            VinculoCanalComercial=(
                modelo_vinculo(vinculos)
            ),
        )


def test_devuelve_vinculo_de_cuenta_autorizada():
    (
        vinculos,
        cuenta_ml_a,
        _cuenta_ml_b,
        _cuenta_tn,
    ) = crear_datos()

    vinculo = exigir_vinculo_cuenta_tenant(
        1,
        cuenta_ml_a,
        canal="mercadolibre",
        VinculoCanalComercial=(
            modelo_vinculo(vinculos)
        ),
        solo_activo=True,
    )

    assert vinculo.organizacion_id == 1
    assert (
        vinculo.mercado_libre_cuenta_id
        == cuenta_ml_a.id
    )


def test_cuentas_no_duplican_propiedad_tenant():
    ml = Path(
        "models/mercado_libre_cuenta.py"
    ).read_text(encoding="utf-8")
    tn = Path(
        "models/tienda_nube_cuenta.py"
    ).read_text(encoding="utf-8")
    vinculo = Path(
        "models/vinculo_canal_comercial.py"
    ).read_text(encoding="utf-8")

    assert "organizacion_id" not in ml
    assert "organizacion_id" not in tn
    assert (
        "organizacion_id = db.Column("
        in vinculo
    )
    assert (
        "mercado_libre_cuenta_id = "
        "db.Column("
        in vinculo
    )
    assert (
        "tienda_nube_cuenta_id = "
        "db.Column("
        in vinculo
    )
    assert vinculo.count("unique=True") == 2
