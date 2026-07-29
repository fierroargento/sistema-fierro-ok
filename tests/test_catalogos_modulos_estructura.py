from pathlib import Path
from types import SimpleNamespace

import pytest

from services.catalogos_comerciales import (
    centavos_a_importe,
    configurar_precio_catalogo,
    importe_a_centavos,
)
from services.modulos_organizacion import (
    cambiar_estado_modulo,
    modulo_esta_activo,
    modulo_esta_en_prueba,
    normalizar_estado_modulo,
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


def test_modulos_solo_habilitan_produccion_en_activo():
    modulo = SimpleNamespace(
        estado="desactivado",
        detalle="",
    )

    assert modulo_esta_activo(modulo) is False
    assert modulo_esta_en_prueba(modulo) is False

    modulo.estado = "prueba"

    assert modulo_esta_activo(modulo) is False
    assert modulo_esta_en_prueba(modulo) is True

    modulo.estado = "activo"

    assert modulo_esta_activo(modulo) is True
    assert modulo_esta_en_prueba(modulo) is False


def test_cambio_de_estado_persiste():
    modulo = SimpleNamespace(
        estado="desactivado",
        detalle="",
    )
    session = SessionFake()

    resultado = cambiar_estado_modulo(
        modulo,
        "prueba",
        db_session=session,
        detalle="Validación interna",
    )

    assert resultado is modulo
    assert modulo.estado == "prueba"
    assert modulo.detalle == "Validación interna"
    assert session.commits == 1
    assert session.rollbacks == 0


def test_cambio_de_estado_revierte_si_falla_commit():
    modulo = SimpleNamespace(
        estado="desactivado",
        detalle="",
    )
    session = SessionFake(
        RuntimeError("fallo commit")
    )

    with pytest.raises(
        RuntimeError,
        match="fallo commit",
    ):
        cambiar_estado_modulo(
            modulo,
            "activo",
            db_session=session,
        )

    assert session.commits == 1
    assert session.rollbacks == 1


def test_estado_invalido_se_rechaza():
    with pytest.raises(
        ValueError,
        match="Estado de módulo inválido",
    ):
        normalizar_estado_modulo(
            "habilitado-a-medias"
        )


@pytest.mark.parametrize(
    ("importe", "centavos"),
    [
        ("0", 0),
        ("10", 1000),
        ("10.50", 1050),
        ("10,50", 1050),
        ("1234.567", 123457),
    ],
)
def test_importes_se_guardan_sin_error_flotante(
    importe,
    centavos,
):
    assert importe_a_centavos(importe) == centavos
    assert importe_a_centavos(
        centavos_a_importe(centavos)
    ) == centavos


def test_configura_precio_y_precio_lista():
    inclusion = SimpleNamespace(
        precio_centavos=0,
        precio_lista_centavos=None,
    )

    configurar_precio_catalogo(
        inclusion,
        precio="12500.75",
        precio_lista="15000",
    )

    assert inclusion.precio_centavos == 1250075
    assert (
        inclusion.precio_lista_centavos
        == 1500000
    )


def test_modelos_nuevos_nacen_inactivos():
    catalogo = Path(
        "models/catalogo.py"
    ).read_text(encoding="utf-8")

    inclusion = Path(
        "models/catalogo_producto.py"
    ).read_text(encoding="utf-8")

    modulo = Path(
        "models/modulo_organizacion.py"
    ).read_text(encoding="utf-8")

    assert 'default="desactivado"' in catalogo
    assert "default=False" in inclusion
    assert 'default="desactivado"' in modulo


def test_app_registra_modelos_y_modulos_sin_runtime():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )

    assert (
        "from models.catalogo import Catalogo"
        in app
    )
    assert (
        "from models.catalogo_producto "
        "import CatalogoProducto"
        in app
    )
    assert (
        "from models.modulo_organizacion "
        "import ModuloOrganizacion"
        in app
    )
    assert (
        "asegurar_modulos_iniciales("
        in app
    )

    bloque_arranque = app[
        app.index("with app.app_context():"):
    ]

    assert (
        bloque_arranque.index(
            "asegurar_estructura_empresarial_inicial("
        )
        < bloque_arranque.index(
            "asegurar_modulos_iniciales("
        )
    )
