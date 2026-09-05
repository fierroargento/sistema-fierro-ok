from pathlib import Path
from types import SimpleNamespace

import pytest

from services.asignacion_tenant_pedidos import (
    aplicar_propuesta_tenant,
    aprobar_propuesta_tenant,
    preparar_propuestas_tenant,
)


class Columna:
    def __eq__(self, _otro): return self
    def in_(self, _valores): return self
    def is_(self, _valor): return self


class Query:
    def __init__(self, datos):
        self.datos = datos

    def all(self): return list(self.datos)
    def yield_per(self, _cantidad): return iter(self.datos)
    def filter(self, *_args): return self
    def order_by(self, *_args): return self
    def get(self, identificador):
        return next((item for item in self.datos if item.id == identificador), None)
    def filter_by(self, **filtros):
        return Query([
            item for item in self.datos
            if all(getattr(item, clave) == valor for clave, valor in filtros.items())
        ])
    def first(self): return self.datos[0] if self.datos else None


class PedidoModelo:
    organizacion_id = Columna()
    query = Query([])


class VinculoModelo:
    query = Query([])


class PropuestaModelo:
    pedido_id = Columna()
    estado = Columna()
    query = Query([])

    def __init__(self, **datos):
        self.__dict__.update(datos)
        self.id = datos.get("id")


class Sesion:
    def __init__(self):
        self.agregados = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, objeto): self.agregados.append(objeto)
    def commit(self): self.commits += 1
    def flush(self): pass
    def rollback(self): self.rollbacks += 1


def _vinculo():
    return SimpleNamespace(
        organizacion_id=10, unidad_negocio_id=100,
        mercado_libre_cuenta_id=5, tienda_nube_cuenta_id=None,
    )


def _pedido():
    return SimpleNamespace(
        id=1, organizacion_id=None, unidad_negocio_id=None,
        ml_cuenta_id=5, tn_cuenta_id=None,
    )


def test_preparar_y_aprobar_no_modifican_pedido_aplicar_si():
    pedido, vinculo, sesion = _pedido(), _vinculo(), Sesion()
    PedidoModelo.query = Query([pedido])
    VinculoModelo.query = Query([vinculo])
    PropuestaModelo.query = Query([])

    cantidad = preparar_propuestas_tenant(
        10, Pedido=PedidoModelo, VinculoCanalComercial=VinculoModelo,
        AsignacionTenantPedido=PropuestaModelo, db_session=sesion,
        usuario=SimpleNamespace(id=7, username="admin"),
    )
    assert cantidad == 1
    propuesta = sesion.agregados[0]
    propuesta.id = 50
    PropuestaModelo.query = Query([propuesta])
    assert pedido.organizacion_id is None

    aprobar_propuesta_tenant(
        50, 10, Pedido=PedidoModelo, VinculoCanalComercial=VinculoModelo,
        AsignacionTenantPedido=PropuestaModelo, db_session=sesion,
        usuario=SimpleNamespace(id=7, username="admin"),
    )
    assert propuesta.estado == "aprobada"
    assert pedido.organizacion_id is None

    aplicar_propuesta_tenant(
        50, 10, confirmacion="ASIGNAR", Pedido=PedidoModelo,
        VinculoCanalComercial=VinculoModelo,
        AsignacionTenantPedido=PropuestaModelo, db_session=sesion,
        usuario=SimpleNamespace(id=7, username="admin"),
    )
    assert pedido.organizacion_id == 10
    assert pedido.unidad_negocio_id == 100
    assert propuesta.estado == "aplicada"


def test_aplicar_exige_confirmacion_y_estado_aprobado():
    propuesta = PropuestaModelo(
        id=50, pedido_id=1, organizacion_id=10, unidad_negocio_id=100,
        estado="aprobada", ml_cuenta_id_snapshot=5, tn_cuenta_id_snapshot=None,
    )
    PropuestaModelo.query = Query([propuesta])
    with pytest.raises(ValueError, match="ASIGNAR"):
        aplicar_propuesta_tenant(
            50, 10, confirmacion="", Pedido=PedidoModelo,
            VinculoCanalComercial=VinculoModelo,
            AsignacionTenantPedido=PropuestaModelo, db_session=Sesion(),
            usuario=SimpleNamespace(id=7, username="admin"),
        )


def test_contrato_no_contiene_transporte_externo():
    servicio = Path("services/asignacion_tenant_pedidos.py").read_text(encoding="utf-8")
    for prohibido in ("requests", "oauth", "webhook", "access_token", "mercadopago"):
        assert prohibido not in servicio.lower()
    assert "ASIGNAR" in servicio
