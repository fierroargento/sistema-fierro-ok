from pathlib import Path
from types import SimpleNamespace

from models.configuracion_sistema import (
    ConfiguracionSistema,
)
from modules.transportes import selector


class QueryFake:
    def __init__(self, resultado=None, error=None):
        self.resultado = resultado
        self.error = error
        self.filtros = None

    def filter_by(self, **filtros):
        self.filtros = filtros
        if self.error:
            raise self.error
        return self

    def first(self):
        return self.resultado


class ConfiguracionFake:
    query = QueryFake()


def test_modelo_conserva_tabla_y_columnas():
    assert ConfiguracionSistema.__tablename__ == (
        "configuracion_sistema"
    )

    for nombre in (
        "id",
        "clave",
        "valor",
        "descripcion",
        "actualizado_at",
    ):
        assert hasattr(ConfiguracionSistema, nombre)

    fuente = Path(
        "models/configuracion_sistema.py"
    ).read_text(encoding="utf-8-sig")

    assert "class ConfiguracionSistema(db.Model):" in fuente
    assert '__tablename__ = "configuracion_sistema"' in fuente
    assert "primary_key=True" in fuente
    assert "unique=True" in fuente
    assert "nullable=False" in fuente
    assert fuente.count(
        "default=ahora_utc_naive"
    ) == 1
    assert fuente.count(
        "onupdate=ahora_utc_naive"
    ) == 1


def test_cfg_float_lee_modelo_extraido(
    monkeypatch,
):
    consulta = QueryFake(
        SimpleNamespace(valor="12,5"),
    )
    ConfiguracionFake.query = consulta

    monkeypatch.setattr(
        selector,
        "ConfiguracionSistema",
        ConfiguracionFake,
    )

    resultado = selector._cfg_float(
        "MAX_COSTO",
        9.0,
    )

    assert resultado == 12.5
    assert consulta.filtros == {
        "clave": "MAX_COSTO",
    }


def test_cfg_float_usa_default_si_consulta_falla(
    monkeypatch,
):
    ConfiguracionFake.query = QueryFake(
        error=RuntimeError("fallo controlado"),
    )

    monkeypatch.setattr(
        selector,
        "ConfiguracionSistema",
        ConfiguracionFake,
    )

    assert selector._cfg_float(
        "MAX_COSTO",
        9.0,
    ) == 9.0


def test_selector_no_importa_modelo_desde_app():
    texto = Path(
        "modules/transportes/selector.py"
    ).read_text(encoding="utf-8-sig")

    assert (
        "from models.configuracion_sistema import "
        "ConfiguracionSistema"
        in texto
    )
    assert (
        "from app import ConfiguracionSistema"
        not in texto
    )
