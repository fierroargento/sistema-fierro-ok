from types import SimpleNamespace

import pytest

from services.integraciones_tenant import (
    asegurar_vinculo_ml_oauth,
)
from services.vinculos_canales import (
    CANAL_MERCADO_LIBRE,
)


class Consulta:
    def __init__(self, resultado=None):
        self.resultado = resultado
        self.filtros = None

    def filter_by(self, **filtros):
        self.filtros = filtros
        return self

    def first(self):
        return self.resultado


class ModeloVinculo:
    query = Consulta()

    def __init__(self, **datos):
        for nombre, valor in datos.items():
            setattr(self, nombre, valor)


class Sesion:
    def __init__(self):
        self.agregados = []

    def add(self, registro):
        self.agregados.append(registro)


def _datos():
    organizacion = SimpleNamespace(id=10)
    unidad = SimpleNamespace(
        id=20,
        organizacion_id=10,
    )
    cuenta = SimpleNamespace(
        id=30,
        nickname="NAUTICA_DEL_PLATA",
        user_id_ml="999",
    )

    return organizacion, unidad, cuenta


def test_crea_vinculo_nuevo_desactivado():
    organizacion, unidad, cuenta = _datos()
    ModeloVinculo.query = Consulta()
    sesion = Sesion()

    vinculo, creado = (
        asegurar_vinculo_ml_oauth(
            organizacion,
            unidad,
            cuenta,
            VinculoCanalComercial=(
                ModeloVinculo
            ),
            db_session=sesion,
        )
    )

    assert creado is True
    assert sesion.agregados == [vinculo]
    assert vinculo.organizacion_id == 10
    assert vinculo.unidad_negocio_id == 20
    assert vinculo.canal == CANAL_MERCADO_LIBRE
    assert vinculo.mercado_libre_cuenta_id == 30
    assert vinculo.estado == "desactivado"
    assert (
        vinculo.nombre
        == "Mercado Libre - NAUTICA_DEL_PLATA"
    )


def test_conserva_vinculo_existente_compatible():
    organizacion, unidad, cuenta = _datos()
    existente = SimpleNamespace(
        canal=CANAL_MERCADO_LIBRE,
        organizacion_id=10,
        unidad_negocio_id=20,
        estado="activo",
    )
    ModeloVinculo.query = Consulta(existente)
    sesion = Sesion()

    vinculo, creado = (
        asegurar_vinculo_ml_oauth(
            organizacion,
            unidad,
            cuenta,
            VinculoCanalComercial=(
                ModeloVinculo
            ),
            db_session=sesion,
        )
    )

    assert vinculo is existente
    assert creado is False
    assert existente.estado == "activo"
    assert sesion.agregados == []


@pytest.mark.parametrize(
    (
        "organizacion_id",
        "unidad_id",
        "canal",
    ),
    (
        (99, 20, CANAL_MERCADO_LIBRE),
        (10, 88, CANAL_MERCADO_LIBRE),
        (10, 20, "tiendanube"),
    ),
)
def test_rechaza_reasignar_vinculo(
    organizacion_id,
    unidad_id,
    canal,
):
    organizacion, unidad, cuenta = _datos()
    existente = SimpleNamespace(
        canal=canal,
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_id,
        estado="desactivado",
    )
    ModeloVinculo.query = Consulta(existente)
    sesion = Sesion()

    with pytest.raises(
        ValueError,
        match="otro vinculo",
    ):
        asegurar_vinculo_ml_oauth(
            organizacion,
            unidad,
            cuenta,
            VinculoCanalComercial=(
                ModeloVinculo
            ),
            db_session=sesion,
        )

    assert sesion.agregados == []


def test_rechaza_unidad_de_otro_tenant():
    organizacion, unidad, cuenta = _datos()
    unidad.organizacion_id = 77
    ModeloVinculo.query = Consulta()
    sesion = Sesion()

    with pytest.raises(
        ValueError,
        match="no pertenece",
    ):
        asegurar_vinculo_ml_oauth(
            organizacion,
            unidad,
            cuenta,
            VinculoCanalComercial=(
                ModeloVinculo
            ),
            db_session=sesion,
        )

    assert sesion.agregados == []


def test_rechaza_cuenta_sin_id():
    organizacion, unidad, cuenta = _datos()
    cuenta.id = None
    ModeloVinculo.query = Consulta()
    sesion = Sesion()

    with pytest.raises(
        ValueError,
        match="identificador",
    ):
        asegurar_vinculo_ml_oauth(
            organizacion,
            unidad,
            cuenta,
            VinculoCanalComercial=(
                ModeloVinculo
            ),
            db_session=sesion,
        )

    assert sesion.agregados == []
