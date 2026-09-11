from pathlib import Path
from types import SimpleNamespace

import pytest

from services.propuestas_pedidos_tienda_nube import (
    crear_propuestas,
    decidir_propuestas,
    resumir_propuestas,
)


class Sesion:
    def __init__(self):
        self.agregados = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, valor):
        self.agregados.append(valor)

    def flush(self):
        propuesta = self.agregados[-1]
        if getattr(propuesta, "id", None) is None:
            propuesta.id = len(self.agregados)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class Consulta:
    existente = None

    def filter_by(self, **_campos):
        return self

    def first(self):
        return self.existente


class Propuesta:
    query = Consulta()

    def __init__(self, **datos):
        self.id = None
        self.fecha_creacion = datos.pop("fecha_creacion", 1)
        vars(self).update(datos)


class Evento:
    def __init__(self, **datos):
        vars(self).update(datos)


def plan():
    return {
        "tenant": {"organizacion_id": 10, "unidad_negocio_id": 20},
        "lote": {"id": 30, "cuenta_id": 40},
        "firma_plan": "a" * 64,
        "puede_aplicar": False,
        "escrituras": 0,
        "acciones_externas": 0,
        "filas": [
            {"order_id": "TN-1", "numero": "1", "estado": "preparado", "crearia_pedido": True},
            {"order_id": "TN-2", "numero": "2", "estado": "bloqueado", "crearia_pedido": False},
        ],
    }


def test_crea_solo_candidatas_y_no_pedidos():
    Propuesta.query.existente = None
    sesion = Sesion()
    resultado = crear_propuestas(
        plan(), usuario=SimpleNamespace(id=7, username="admin"),
        PropuestaPedidoTiendaNube=Propuesta,
        EventoPropuestaPedidoTiendaNube=Evento, db_session=sesion,
    )
    assert len(resultado["creadas"]) == 1
    assert resultado["pedidos_creados"] == resultado["acciones_externas"] == 0
    assert resultado["creadas"][0].puede_crear_pedido is False
    assert sesion.commits == 1


def test_creacion_es_idempotente():
    Propuesta.query.existente = Propuesta(organizacion_id=10, unidad_negocio_id=20)
    resultado = crear_propuestas(
        plan(), usuario=None, PropuestaPedidoTiendaNube=Propuesta,
        EventoPropuestaPedidoTiendaNube=Evento, db_session=Sesion(),
    )
    assert not resultado["creadas"]
    assert len(resultado["repetidas"]) == 1
    Propuesta.query.existente = None


@pytest.mark.parametrize("campo,valor", [("puede_aplicar", True), ("escrituras", 1), ("acciones_externas", 1)])
def test_bloquea_planes_con_efectos(campo, valor):
    documento = plan()
    documento[campo] = valor
    with pytest.raises(ValueError):
        crear_propuestas(
            documento, usuario=None, PropuestaPedidoTiendaNube=Propuesta,
            EventoPropuestaPedidoTiendaNube=Evento, db_session=Sesion(),
        )


def test_aprobacion_masiva_es_interna_y_auditable():
    propuestas = [Propuesta(id=1, organizacion_id=10, unidad_negocio_id=20, estado="preparada", puede_crear_pedido=False)]
    sesion = Sesion()
    resultado = decidir_propuestas(
        propuestas, "aprobar", "", organizacion_id=10, unidad_negocio_id=20,
        usuario=SimpleNamespace(id=7, username="admin"),
        EventoPropuestaPedidoTiendaNube=Evento, db_session=sesion,
    )
    assert propuestas[0].estado == "aprobada"
    assert propuestas[0].puede_crear_pedido is False
    assert resultado["pedidos_creados"] == resultado["acciones_externas"] == 0
    assert sesion.commits == 1


def test_decision_revalida_todo_antes_de_mutar():
    propias = Propuesta(id=1, organizacion_id=10, unidad_negocio_id=20, estado="preparada", puede_crear_pedido=False)
    ajena = Propuesta(id=2, organizacion_id=99, unidad_negocio_id=20, estado="preparada", puede_crear_pedido=False)
    sesion = Sesion()
    with pytest.raises(ValueError):
        decidir_propuestas(
            [propias, ajena], "aprobar", "", organizacion_id=10, unidad_negocio_id=20,
            usuario=None, EventoPropuestaPedidoTiendaNube=Evento, db_session=sesion,
        )
    assert propias.estado == "preparada"
    assert sesion.rollbacks == 1


def test_rechazo_y_archivo_exigen_motivo():
    propuesta = Propuesta(id=1, organizacion_id=10, unidad_negocio_id=20, estado="preparada", puede_crear_pedido=False)
    with pytest.raises(ValueError):
        decidir_propuestas(
            [propuesta], "rechazar", "", organizacion_id=10, unidad_negocio_id=20,
            usuario=None, EventoPropuestaPedidoTiendaNube=Evento, db_session=Sesion(),
        )


def test_resumen_excluye_otro_tenant():
    propias = Propuesta(id=1, organizacion_id=10, unidad_negocio_id=20, estado="preparada")
    ajena = Propuesta(id=2, organizacion_id=99, unidad_negocio_id=20, estado="aprobada")
    resumen = resumir_propuestas([ajena, propias], organizacion_id=10, unidad_negocio_id=20)
    assert resumen["total"] == resumen["preparadas"] == 1
    assert resumen["aprobadas"] == resumen["pedidos_creados"] == 0


def test_integracion_estatica_y_contrato_desconectado():
    raiz = Path(__file__).resolve().parents[1]
    servicio = (raiz / "services/propuestas_pedidos_tienda_nube.py").read_text(encoding="utf-8")
    modelo = (raiz / "models/propuesta_pedido_tienda_nube.py").read_text(encoding="utf-8")
    rutas = (raiz / "modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    plantilla = (raiz / "templates/admin_propuestas_pedidos_tienda_nube.html").read_text(encoding="utf-8")
    for prohibido in ("requests.", "urlopen", "access_token", "client_secret", "Pedido.query"):
        assert prohibido not in servicio
    assert "puede_crear_pedido = false" in modelo
    assert "propuestas_pedidos_tienda_nube_comercial" in rutas
    assert "Canales externos bloqueados" in plantilla
    assert "No reserva inventario" in plantilla
