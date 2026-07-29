from pathlib import Path
from types import SimpleNamespace

import pytest

from services.vinculos_canales import (
    cambiar_estado_vinculo,
    validar_cuenta_exclusiva,
    validar_dependencias_activas,
    validar_pertenencia_organizacion,
    vinculo_habilita_produccion,
)


class SessionFake:
    def __init__(self, error=None):
        self.error = error
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1
        if self.error is not None:
            raise self.error

    def rollback(self):
        self.rollbacks += 1


def crear_vinculo(**cambios):
    datos = {
        "canal": "mercadolibre",
        "estado": "desactivado",
        "detalle": "",
        "unidad_negocio": SimpleNamespace(
            id=10,
            activa=True,
        ),
        "catalogo": None,
        "sucursal_operativa": None,
        "entidad_fiscal": None,
        "mercado_libre_cuenta": (
            SimpleNamespace(
                estado_conexion="conectada",
            )
        ),
        "tienda_nube_cuenta": None,
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def test_vinculo_nuevo_no_habilita_produccion():
    assert (
        vinculo_habilita_produccion(
            crear_vinculo()
        )
        is False
    )


def test_cuenta_debe_corresponder_al_canal():
    cuenta = SimpleNamespace(id=1)

    assert validar_cuenta_exclusiva(
        "mercadolibre",
        mercado_libre_cuenta=cuenta,
    )

    with pytest.raises(
        ValueError,
        match="no puede incluir",
    ):
        validar_cuenta_exclusiva(
            "mercadolibre",
            mercado_libre_cuenta=cuenta,
            tienda_nube_cuenta=cuenta,
        )


def test_rechaza_registros_de_otra_organizacion():
    unidad = SimpleNamespace(
        id=2,
        organizacion_id=1,
    )
    catalogo = SimpleNamespace(
        organizacion_id=99,
        unidad_negocio_id=None,
    )

    with pytest.raises(
        ValueError,
        match="no pertenece",
    ):
        validar_pertenencia_organizacion(
            1,
            unidad_negocio=unidad,
            catalogo=catalogo,
        )


def test_catalogo_debe_corresponder_a_la_unidad():
    unidad = SimpleNamespace(
        id=2,
        organizacion_id=1,
    )
    catalogo = SimpleNamespace(
        organizacion_id=1,
        unidad_negocio_id=3,
    )

    with pytest.raises(
        ValueError,
        match="otra unidad",
    ):
        validar_pertenencia_organizacion(
            1,
            unidad_negocio=unidad,
            catalogo=catalogo,
        )


def test_prueba_no_habilita_produccion():
    vinculo = crear_vinculo()
    session = SessionFake()

    cambiar_estado_vinculo(
        vinculo,
        "prueba",
        db_session=session,
    )

    assert vinculo.estado == "prueba"
    assert vinculo_habilita_produccion(
        vinculo
    ) is False
    assert session.commits == 1


def test_activo_exige_dependencias_activas():
    vinculo = crear_vinculo(
        sucursal_operativa=SimpleNamespace(
            activa=False,
        )
    )

    with pytest.raises(
        ValueError,
        match="sucursal debe estar activa",
    ):
        validar_dependencias_activas(
            vinculo
        )


def test_activo_exige_cuenta_conectada():
    vinculo = crear_vinculo(
        mercado_libre_cuenta=SimpleNamespace(
            estado_conexion="desconectada",
        )
    )

    with pytest.raises(
        ValueError,
        match="debe estar conectada",
    ):
        cambiar_estado_vinculo(
            vinculo,
            "activo",
            db_session=SessionFake(),
        )


def test_commit_fallido_hace_rollback():
    vinculo = crear_vinculo()
    session = SessionFake(
        RuntimeError("fallo commit")
    )

    with pytest.raises(
        RuntimeError,
        match="fallo commit",
    ):
        cambiar_estado_vinculo(
            vinculo,
            "prueba",
            db_session=session,
        )

    assert session.commits == 1
    assert session.rollbacks == 1


def test_modelo_nace_desactivado():
    modelo = Path(
        "models/vinculo_canal_comercial.py"
    ).read_text(encoding="utf-8")

    assert 'default="desactivado"' in modelo
    assert (
        'ForeignKey("mercado_libre_cuenta.id")'
        in modelo
    )
    assert (
        'ForeignKey("tienda_nube_cuenta.id")'
        in modelo
    )


def test_vinculos_no_son_consumidos_por_runtime():
    archivos_runtime = [
        "services/ml_importacion.py",
        "services/ml_claims.py",
        "modules/whatsapp/runtime.py",
    ]

    for nombre in archivos_runtime:
        contenido = Path(nombre).read_text(
            encoding="utf-8-sig"
        )
        assert "VinculoCanalComercial" not in contenido
