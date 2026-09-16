from types import SimpleNamespace

import pytest

from services.contexto_canal_tenant import (
    ContextoCanalError,
    resolver_contexto_cuenta,
    validar_pedido_en_contexto,
)


class Consulta:
    def __init__(self, resultados):
        self.resultados = resultados
        self.filtros = None

    def filter_by(self, **filtros):
        self.filtros = filtros
        return self

    def all(self):
        return self.resultados


def modelo_vinculo(resultados):
    return SimpleNamespace(query=Consulta(resultados))


def test_resuelve_unico_vinculo_activo_tn():
    vinculo = SimpleNamespace(organizacion_id=4, unidad_negocio_id=9)
    modelo = modelo_vinculo([vinculo])
    resultado = resolver_contexto_cuenta(
        SimpleNamespace(id=12), canal="tiendanube", VinculoCanalComercial=modelo,
    )
    assert resultado is vinculo
    assert modelo.query.filtros == {
        "canal": "tiendanube", "estado": "activo", "tienda_nube_cuenta_id": 12,
    }


@pytest.mark.parametrize("vinculos", [[], [SimpleNamespace(), SimpleNamespace()]])
def test_rechaza_cuenta_sin_vinculo_unico(vinculos):
    with pytest.raises(ContextoCanalError, match="exactamente un vinculo"):
        resolver_contexto_cuenta(
            SimpleNamespace(id=2),
            canal="mercadolibre",
            VinculoCanalComercial=modelo_vinculo(vinculos),
        )


def test_rechaza_pedido_de_otra_organizacion_o_unidad():
    vinculo = SimpleNamespace(organizacion_id=1, unidad_negocio_id=2)
    with pytest.raises(ContextoCanalError, match="otra organizacion"):
        validar_pedido_en_contexto(
            SimpleNamespace(organizacion_id=8, unidad_negocio_id=2), vinculo,
        )
    with pytest.raises(ContextoCanalError, match="otra unidad"):
        validar_pedido_en_contexto(
            SimpleNamespace(organizacion_id=1, unidad_negocio_id=7), vinculo,
        )


def test_app_propaga_tenant_en_tn_y_webhooks_ml():
    from pathlib import Path

    app = Path("app.py").read_text(encoding="utf-8-sig")
    assert "organizacion_id=vinculo_origen.organizacion_id" in app
    assert "unidad_negocio_id=vinculo_origen.unidad_negocio_id" in app
    assert "cuenta_tn_desde_webhook(data)" in app
    assert "Pedido.organizacion_id == organizacion_id_webhook" in app
    assert "Pedido.organizacion_id == organizacion_id" in app
