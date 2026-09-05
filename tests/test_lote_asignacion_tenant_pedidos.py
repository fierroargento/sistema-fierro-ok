from pathlib import Path
from types import SimpleNamespace

import pytest

from services.asignacion_tenant_pedidos import (
    aplicar_lote_tenant,
    aprobar_lote_tenant,
    previsualizar_lote_tenant,
)


class Columna:
    def __eq__(self, _otro): return self
    def in_(self, _valores): return self


class Query:
    def __init__(self, datos):
        self.datos = datos

    def all(self): return list(self.datos)
    def get(self, identificador):
        return next((item for item in self.datos if item.id == identificador), None)
    def filter_by(self, **filtros):
        return Query([
            item for item in self.datos
            if all(getattr(item, clave) == valor for clave, valor in filtros.items())
        ])
    def first(self): return self.datos[0] if self.datos else None


class PedidoModelo:
    query = Query([])


class VinculoModelo:
    query = Query([])


class PropuestaModelo:
    pedido_id = Columna()
    estado = Columna()
    query = Query([])


class Sesion:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


USUARIO = SimpleNamespace(id=7, username="admin")


def _escenario(estado="preparada"):
    pedidos = [
        SimpleNamespace(
            id=1, organizacion_id=None, unidad_negocio_id=None,
            ml_cuenta_id=5, tn_cuenta_id=None,
        ),
        SimpleNamespace(
            id=2, organizacion_id=None, unidad_negocio_id=None,
            ml_cuenta_id=5, tn_cuenta_id=None,
        ),
    ]
    propuestas = [
        SimpleNamespace(
            id=51, pedido_id=1, organizacion_id=10, unidad_negocio_id=100,
            estado=estado, ml_cuenta_id_snapshot=5, tn_cuenta_id_snapshot=None,
        ),
        SimpleNamespace(
            id=52, pedido_id=2, organizacion_id=10, unidad_negocio_id=100,
            estado=estado, ml_cuenta_id_snapshot=5, tn_cuenta_id_snapshot=None,
        ),
    ]
    PedidoModelo.query = Query(pedidos)
    PropuestaModelo.query = Query(propuestas)
    VinculoModelo.query = Query([
        SimpleNamespace(
            organizacion_id=10, unidad_negocio_id=100,
            mercado_libre_cuenta_id=5, tienda_nube_cuenta_id=None,
        )
    ])
    return pedidos, propuestas


def _dependencias(sesion):
    return {
        "Pedido": PedidoModelo,
        "VinculoCanalComercial": VinculoModelo,
        "AsignacionTenantPedido": PropuestaModelo,
        "db_session": sesion,
        "usuario": USUARIO,
    }


def test_previsualizacion_no_escribe_y_deduplica_ids():
    _pedidos, propuestas = _escenario()
    vista = previsualizar_lote_tenant(
        [51, "51", 52], 10, estado_requerido="preparada",
        Pedido=PedidoModelo, VinculoCanalComercial=VinculoModelo,
        AsignacionTenantPedido=PropuestaModelo,
    )
    assert vista["valido"] is True
    assert vista["ids"] == [51, 52]
    assert vista["escrituras_realizadas"] == 0
    assert [item.estado for item in propuestas] == ["preparada", "preparada"]


def test_aprobacion_del_lote_es_conjunta_y_no_asigna_pedidos():
    pedidos, propuestas = _escenario()
    sesion = Sesion()
    cantidad = aprobar_lote_tenant([51, 52], 10, **_dependencias(sesion))
    assert cantidad == 2
    assert sesion.commits == 1
    assert [item.estado for item in propuestas] == ["aprobada", "aprobada"]
    assert [item.organizacion_id for item in pedidos] == [None, None]


def test_un_elemento_obsoleto_bloquea_todo_antes_de_mutar():
    pedidos, propuestas = _escenario(estado="aprobada")
    pedidos[1].ml_cuenta_id = 99
    sesion = Sesion()
    with pytest.raises(ValueError, match="lote completo fue bloqueado"):
        aplicar_lote_tenant(
            [51, 52], 10, confirmacion="ASIGNAR LOTE",
            **_dependencias(sesion),
        )
    assert sesion.commits == 0
    assert [item.organizacion_id for item in pedidos] == [None, None]
    assert [item.estado for item in propuestas] == ["aprobada", "aprobada"]


def test_aplicacion_valida_es_un_solo_commit():
    pedidos, propuestas = _escenario(estado="aprobada")
    sesion = Sesion()
    cantidad = aplicar_lote_tenant(
        [51, 52], 10, confirmacion="ASIGNAR LOTE",
        **_dependencias(sesion),
    )
    assert cantidad == 2
    assert sesion.commits == 1
    assert [item.organizacion_id for item in pedidos] == [10, 10]
    assert [item.unidad_negocio_id for item in pedidos] == [100, 100]
    assert [item.estado for item in propuestas] == ["aplicada", "aplicada"]


def test_aplicacion_masiva_exige_confirmacion_especifica():
    _escenario(estado="aprobada")
    with pytest.raises(ValueError, match="ASIGNAR LOTE"):
        aplicar_lote_tenant(
            [51, 52], 10, confirmacion="ASIGNAR",
            **_dependencias(Sesion()),
        )


def test_contrato_web_es_preparatorio_y_desconectado():
    rutas = Path("modules/admin/estructura/routes.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_estructura.html").read_text(encoding="utf-8")
    vista = Path(
        "templates/admin_previsualizacion_asignaciones_pedidos.html"
    ).read_text(encoding="utf-8")
    assert "previsualizar_asignaciones" in rutas
    assert "previsualizar_lote_tenant" in rutas
    assert 'form="form-lote-asignaciones"' in panel
    assert "ASIGNAR LOTE" in vista
    assert "No se aplicará parcialmente" in vista
    texto = (rutas + panel + vista).lower()
    for prohibido in ("requests.", "access_token", "mercadopago", "oauth"):
        assert prohibido not in texto
