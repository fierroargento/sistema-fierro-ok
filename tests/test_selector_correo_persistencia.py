import sys
import types
from types import SimpleNamespace

from modules.transportes import selector
from services import correo_argentino_operacion
from services import workflow_correo_sucursal_oferta


class SessionCommitFallido:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1
        raise RuntimeError("fallo simulado de persistencia")

    def rollback(self):
        self.rollbacks += 1


class PedidoFake:
    def __init__(self):
        self.oferta_aplicada = False


def test_marcar_escalado_hace_rollback_si_falla_persistencia(
    monkeypatch,
):
    session = SessionCommitFallido()
    db_fake = types.SimpleNamespace(session=session)

    monkeypatch.setitem(
        sys.modules,
        "app",
        types.SimpleNamespace(db=db_fake),
    )

    pedido = SimpleNamespace(
        ia_requiere_operador=False,
        ml_mensajes_pendientes=False,
        wa_estado="",
        ia_resumen="",
    )

    selector._marcar_escalado(
        pedido,
        "Revisión manual de transporte",
    )

    assert session.commits == 1
    assert session.rollbacks == 1


def test_preparar_oferta_correo_exitosa_no_hace_commit(
    monkeypatch,
):
    session = SessionCommitFallido()

    monkeypatch.setattr(
        selector,
        "correo_pp6040_habilitado",
        lambda: True,
    )
    monkeypatch.setattr(
        selector,
        "pedido_contiene_pp6040",
        lambda pedido: False,
    )
    monkeypatch.setattr(
        selector,
        "obtener_sucursales_correo_por_pedido",
        lambda pedido: [{"agency_id": "A1"}],
    )
    monkeypatch.setattr(
        correo_argentino_operacion,
        "obtener_preferencias_operativas_correo",
        lambda: {"cantidad_sucursales_cliente": 3},
    )
    monkeypatch.setattr(
        workflow_correo_sucursal_oferta,
        "preparar_oferta_sucursales_correo",
        lambda sucursales, limite=3: SimpleNamespace(
            ids=["A1"],
            mensaje="Elegí una sucursal",
        ),
    )

    def aplicar_oferta(
        pedido,
        sucursales,
        ids,
        canal_origen="ml",
    ):
        pedido.oferta_aplicada = True
        return True

    monkeypatch.setattr(
        workflow_correo_sucursal_oferta,
        "aplicar_oferta_sucursales_correo_al_pedido",
        aplicar_oferta,
    )

    pedido = PedidoFake()

    resultado = (
        selector.preparar_oferta_sucursales_correo_pedido(
            pedido,
            canal_origen="ml",
        )
    )

    assert pedido.oferta_aplicada is True
    assert resultado.ok is True
    assert resultado.estado == "preparada"
    assert resultado.mensaje == "Elegí una sucursal"
    assert resultado.requiere_persistencia is True
    assert session.commits == 0
    assert session.rollbacks == 0
