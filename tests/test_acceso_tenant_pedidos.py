from pathlib import Path
from types import SimpleNamespace

import pytest

from services.acceso_tenant_pedidos import (
    consulta_pedidos_tenant,
    obtener_pedido_tenant,
    validar_pedido_en_tenant,
)


class Query:
    def __init__(self, datos):
        self.datos = list(datos)

    def filter_by(self, **filtros):
        return Query([
            item for item in self.datos
            if all(getattr(item, clave) == valor for clave, valor in filtros.items())
        ])

    def first(self):
        return self.datos[0] if self.datos else None

    def all(self):
        return list(self.datos)


class PedidoModelo:
    query = Query([])


def _pedidos():
    return [
        SimpleNamespace(id=1, organizacion_id=10, unidad_negocio_id=100),
        SimpleNamespace(id=2, organizacion_id=20, unidad_negocio_id=200),
        SimpleNamespace(id=3, organizacion_id=None, unidad_negocio_id=None),
    ]


def test_consulta_exige_tenant_y_no_devuelve_otros_ni_legacy():
    PedidoModelo.query = Query(_pedidos())
    assert [p.id for p in consulta_pedidos_tenant(PedidoModelo, 10).all()] == [1]
    with pytest.raises(ValueError, match="organización"):
        consulta_pedidos_tenant(PedidoModelo, None)


def test_obtener_por_id_tambien_filtra_organizacion():
    PedidoModelo.query = Query(_pedidos())
    assert obtener_pedido_tenant(1, 10, Pedido=PedidoModelo).id == 1
    assert obtener_pedido_tenant(2, 10, Pedido=PedidoModelo) is None
    assert obtener_pedido_tenant(3, 10, Pedido=PedidoModelo) is None


def test_unidad_activa_es_una_frontera_adicional():
    PedidoModelo.query = Query(_pedidos())
    assert obtener_pedido_tenant(
        1, 10, unidad_negocio_id=100, Pedido=PedidoModelo,
    ).id == 1
    assert obtener_pedido_tenant(
        1, 10, unidad_negocio_id=101, Pedido=PedidoModelo,
    ) is None


def test_validador_rechaza_objeto_cargado_de_otro_tenant():
    pedido = _pedidos()[1]
    with pytest.raises(ValueError, match="no pertenece"):
        validar_pedido_en_tenant(pedido, 10)


def test_ruta_modular_de_edicion_usa_guardian_tenant():
    ruta = Path("modules/pedidos/edicion_cliente_routes.py").read_text(
        encoding="utf-8"
    )
    assert "resolver_tenant_usuario(" in ruta
    assert 'session.get("organizacion_id")' in ruta
    assert "obtener_pedido_tenant(" in ruta
    assert "Pedido.query.get_or_404" not in ruta


def test_guardian_no_contiene_transporte_externo():
    texto = Path("services/acceso_tenant_pedidos.py").read_text(encoding="utf-8")
    for prohibido in ("requests", "oauth", "webhook", "access_token", "mercadopago"):
        assert prohibido not in texto.lower()
