import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from modules.automation.jobs import ml_messages
from modules.automation.jobs.ml_messages import ejecutar_job_ml_mensajes
from services import ml_cuentas


class ExprFake:
    def __or__(self, other):
        return self


class CampoFake:
    def __eq__(self, other):
        return ExprFake()

    def notin_(self, valores):
        return ExprFake()


class QueryFake:
    def __init__(self, resultados_por_all):
        self.resultados_por_all = list(resultados_por_all)

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        if self.resultados_por_all:
            return self.resultados_por_all.pop(0)
        return []


class PedidoFake:
    canal = CampoFake()
    ia_esperando_respuesta = CampoFake()
    ml_mensajes_pendientes = CampoFake()
    estado = CampoFake()
    ml_tipo = CampoFake()


class AppContextFake:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FlaskAppFake:
    def app_context(self):
        return AppContextFake()


class SessionFake:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.removes = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def remove(self):
        self.removes += 1


class DbFake:
    def __init__(self):
        self.session = SessionFake()


def instalar_app_fake(monkeypatch, pedidos_esperando, pedidos, mensajes_fn, analizar_fn):
    modulo_app = ModuleType("app")

    PedidoFake.query = QueryFake([
        pedidos_esperando,
        pedidos,
    ])

    monkeypatch.setattr(
        ml_messages,
        "Pedido",
        PedidoFake,
    )
    modulo_app.ia_escalar_si_timeout_operativo = lambda *args, **kwargs: None
    modulo_app.ml_obtener_mensajes_pack_para_ia = mensajes_fn
    modulo_app.ia_analizar_ultimo_mensaje_pedido = analizar_fn

    monkeypatch.setitem(sys.modules, "app", modulo_app)


def test_job_ml_mensajes_usa_seller_id_por_pedido(monkeypatch):
    p1 = SimpleNamespace(
        id=1,
        canal="Mercado Libre",
        ml_cuenta_id=1,
        ml_seller_id="111",
        wa_estado="",
        ml_pack_id="pack-1",
        id_venta="order-1",
    )
    p2 = SimpleNamespace(
        id=2,
        canal="Mercado Libre",
        ml_cuenta_id=2,
        ml_seller_id="222",
        wa_estado="",
        ml_pack_id="pack-2",
        id_venta="order-2",
    )

    seller_por_pedido = {
        1: "111",
        2: "222",
    }

    monkeypatch.setattr(
        ml_cuentas,
        "seller_id_pedido",
        lambda pedido: seller_por_pedido[pedido.id],
    )

    monkeypatch.setattr(
        "services.canal_manager.ml_puede_gobernar_timeout",
        lambda pedido: True,
    )

    llamadas_mensajes = []
    llamadas_analisis = []

    def mensajes_fn(id_chat, seller_id=None):
        llamadas_mensajes.append((id_chat, seller_id))
        return [{"text": f"mensaje-{seller_id}"}]

    def analizar_fn(pedido, mensajes, seller_id=None, forzar=False):
        llamadas_analisis.append((pedido.id, seller_id, forzar))
        return True

    instalar_app_fake(
        monkeypatch,
        pedidos_esperando=[],
        pedidos=[p1, p2],
        mensajes_fn=mensajes_fn,
        analizar_fn=analizar_fn,
    )

    db = DbFake()
    ejecutar_job_ml_mensajes(FlaskAppFake(), db)

    assert llamadas_mensajes == [
        ("pack-1", "111"),
        ("pack-2", "222"),
    ]

    assert llamadas_analisis == [
        (1, "111", False),
        (2, "222", False),
    ]

    assert db.session.commits == 2
    assert db.session.removes == 1


def test_job_ml_mensajes_saltea_pedido_sin_cuenta_valida(monkeypatch):
    p1 = SimpleNamespace(
        id=1,
        canal="Mercado Libre",
        ml_cuenta_id=None,
        ml_seller_id="",
        wa_estado="",
        ml_pack_id="pack-1",
        id_venta="order-1",
    )
    p2 = SimpleNamespace(
        id=2,
        canal="Mercado Libre",
        ml_cuenta_id=2,
        ml_seller_id="222",
        wa_estado="",
        ml_pack_id="pack-2",
        id_venta="order-2",
    )

    def seller_fake(pedido):
        if pedido.id == 1:
            raise ml_cuentas.MLCuentaNoAsignada("sin cuenta")
        return "222"

    monkeypatch.setattr(ml_cuentas, "seller_id_pedido", seller_fake)

    monkeypatch.setattr(
        "services.canal_manager.ml_puede_gobernar_timeout",
        lambda pedido: True,
    )

    llamadas_mensajes = []

    def mensajes_fn(id_chat, seller_id=None):
        llamadas_mensajes.append((id_chat, seller_id))
        return [{"text": "ok"}]

    def analizar_fn(pedido, mensajes, seller_id=None, forzar=False):
        return True

    instalar_app_fake(
        monkeypatch,
        pedidos_esperando=[],
        pedidos=[p1, p2],
        mensajes_fn=mensajes_fn,
        analizar_fn=analizar_fn,
    )

    db = DbFake()
    ejecutar_job_ml_mensajes(FlaskAppFake(), db)

    assert llamadas_mensajes == [
        ("pack-2", "222"),
    ]

    assert db.session.commits == 1
    assert db.session.removes == 1

def test_job_ml_mensajes_usa_pedido_canonico():
    texto = Path(
        "modules/automation/jobs/ml_messages.py"
    ).read_text(encoding="utf-8-sig")

    assert texto.count(
        "from models.pedido import Pedido"
    ) == 1
    assert "\n                Pedido,\n" not in texto
