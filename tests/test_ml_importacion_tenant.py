from pathlib import Path
from types import SimpleNamespace

import pytest

from services.ml_importacion import (
    ml_pedido_existente_por_order_id_service,
)


class Query:
    def __init__(self, datos):
        self.datos = list(datos)

    def filter_by(self, **filtros):
        return Query([
            item for item in self.datos
            if all(getattr(item, clave, None) == valor for clave, valor in filtros.items())
        ])

    def order_by(self, *args):
        return self

    def first(self):
        return self.datos[0] if self.datos else None


class Id:
    @staticmethod
    def asc():
        return "id"


class Pedido:
    id = Id()
    query = Query([])


def test_busqueda_order_no_cruza_organizaciones():
    ajeno = SimpleNamespace(
        id=1, organizacion_id=20, unidad_negocio_id=100,
        canal="Mercado Libre", id_venta="ORDER-1",
    )
    propio = SimpleNamespace(
        id=2, organizacion_id=10, unidad_negocio_id=100,
        canal="Mercado Libre", id_venta="ORDER-1",
    )
    Pedido.query = Query([ajeno, propio])
    assert ml_pedido_existente_por_order_id_service(
        "ORDER-1", 10, 100, Pedido,
    ) is propio
    with pytest.raises(ValueError, match="organización"):
        ml_pedido_existente_por_order_id_service("ORDER-1", None, 100, Pedido)


def test_busqueda_order_no_cruza_unidades():
    ajeno = SimpleNamespace(
        id=1, organizacion_id=10, unidad_negocio_id=101,
        canal="Mercado Libre", id_venta="ORDER-1",
    )
    propio = SimpleNamespace(
        id=2, organizacion_id=10, unidad_negocio_id=100,
        canal="Mercado Libre", id_venta="ORDER-1",
    )
    Pedido.query = Query([ajeno, propio])
    assert ml_pedido_existente_por_order_id_service(
        "ORDER-1", 10, 100, Pedido,
    ) is propio


def test_cinco_consultas_del_importador_quedaron_particionadas():
    texto = Path("services/ml_importacion.py").read_text(encoding="utf-8")
    assert "Pedido.query" not in texto
    assert texto.count("Pedido, organizacion_id, unidad_negocio_id") == 4


def test_sync_manual_exige_tenant_y_lo_propaga():
    texto = Path("app.py").read_text(encoding="utf-8")
    inicio = texto.index("def ml_sync_manual(")
    fin = texto.index("\ndef ia_datos_detectados_pedido(", inicio)
    bloque = texto[inicio:fin]
    assert "organizacion_id=None" in bloque
    assert "requiere una organización explícita" in bloque
    assert "ml_limpiar_pedidos_ml_no_operables_existentes(organizacion_id)" in bloque
    assert "organizacion_id=organizacion_id" in bloque


def test_upsert_resuelve_vinculo_y_graba_identidad_tenant():
    texto = Path("app.py").read_text(encoding="utf-8")
    inicio = texto.index("def ml_upsert_pedido_desde_order(")
    fin = texto.index("\ndef ml_borrar_pedidos_ml_cargando_importados(", inicio)
    bloque = texto[inicio:fin]
    assert "ml_vinculo_activo_cuenta(" in bloque
    assert "pedido.organizacion_id = organizacion_id" in bloque
    assert "pedido.unidad_negocio_id = vinculo_cuenta.unidad_negocio_id" in bloque
    assert "unidad_negocio_id=unidad_negocio_id" in bloque


def test_webhook_deriva_tenant_desde_cuenta_sin_fallback_global():
    texto = Path("app.py").read_text(encoding="utf-8")
    inicio = texto.index("def ml_sync_pedido_por_order_id_webhook(")
    fin = texto.index("\ndef ml_sync_shipment_por_id_webhook(", inicio)
    bloque = texto[inicio:fin]
    assert "vinculo_cuenta = ml_vinculo_activo_cuenta(api_context.cuenta)" in bloque
    assert "organizacion_id=organizacion_id" in bloque
    assert "order_id, organizacion_id, unidad_negocio_id," in bloque


def test_lote_no_habilita_importaciones_ni_transporte():
    servicio = Path("services/ml_importacion.py").read_text(encoding="utf-8").lower()
    assert "pedido.query" not in servicio
    for prohibido in ("scheduler_enabled = true", "access_token =", "oauth", "requests.post"):
        assert prohibido not in servicio
