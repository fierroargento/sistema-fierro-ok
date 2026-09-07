from pathlib import Path
from types import SimpleNamespace

from services.busqueda_pedidos import buscar_pedido_activo_por_telefono_service


class Campo:
    def notin_(self, valores): return self
    def desc(self): return self


class Query:
    def __init__(self, datos): self.datos = list(datos)
    def filter_by(self, **filtros):
        return Query([x for x in self.datos if all(getattr(x, k, None) == v for k, v in filtros.items())])
    def filter(self, *args): return self
    def order_by(self, *args): return self
    def limit(self, limite): return self
    def all(self): return self.datos


class Pedido:
    estado = Campo()
    id = Campo()
    query = Query([])


def test_telefono_no_encuentra_pedido_de_otro_tenant():
    ajeno = SimpleNamespace(organizacion_id=20, telefono="2920 123456")
    propio = SimpleNamespace(organizacion_id=10, telefono="2920 123456")
    Pedido.query = Query([ajeno, propio])
    assert buscar_pedido_activo_por_telefono_service("2920123456", 10, Pedido) is propio


def test_wrapper_sin_tenant_no_hace_fallback_global():
    texto = Path("services/busqueda_pedidos.py").read_text(encoding="utf-8")
    assert "if organizacion_id is None:\n        return None" in texto
    assert "Pedido.query" not in texto


def test_runtime_solo_busca_si_recibe_organizacion():
    texto = Path("modules/whatsapp/runtime.py").read_text(encoding="utf-8")
    assert "and organizacion_id is not None" in texto
    assert "tel_norm,\n                organizacion_id,\n                Pedido," in texto


def test_no_agrega_transporte_ni_activa_webhook():
    texto = Path("services/busqueda_pedidos.py").read_text(encoding="utf-8").lower()
    for prohibido in ("requests", "oauth", "access_token", "webhook"):
        assert prohibido not in texto
