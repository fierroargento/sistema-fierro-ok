import sys
import types

from modules.transportes import selector


class SessionFake:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class PedidoFake:
    def __init__(self):
        self.empresa_envio = ""
        self.tipo_entrega = ""
        self.costo_envio = 0
        self.costo_envio_sucursal = 0
        self.costo_envio_domicilio = 0
        self.ia_resumen = ""


def test_asignar_transporte_pedido_usa_capa_operativa_correo(monkeypatch):
    session = SessionFake()
    db_fake = types.SimpleNamespace(session=session)
    monkeypatch.setitem(sys.modules, "app", types.SimpleNamespace(db=db_fake))

    monkeypatch.setattr(selector, "correo_pp6040_habilitado", lambda: True)
    monkeypatch.setattr(selector, "pedido_contiene_pp6040", lambda pedido: True)

    monkeypatch.setattr(
        selector,
        "evaluar_decision_correo_pp6040",
        lambda pedido, preferencia_cliente="sucursal": {
            "decision": "sucursal",
            "motivo": "Sucursal/Punto Correo preferido",
            "sucursal": {
                "disponible": True,
                "precio": 13255.0,
                "servicio": "Correo Argentino Clasico",
            },
            "domicilio": {
                "disponible": True,
                "precio": 15957.0,
                "servicio": "Correo Argentino Clasico",
            },
        },
    )

    pedido = PedidoFake()

    ok, mensaje = selector.asignar_transporte_pedido(pedido)

    assert ok is True
    assert mensaje == "Correo Argentino asignado (Sucursal)"
    assert pedido.empresa_envio == "Correo Argentino"
    assert pedido.tipo_entrega == "Sucursal"
    assert pedido.costo_envio == 13255.0
    assert pedido.costo_envio_sucursal == 13255.0
    assert pedido.costo_envio_domicilio == 15957.0
    assert "Correo Argentino evaluado" in pedido.ia_resumen
    assert session.committed is True
    assert session.rolled_back is False


def test_preparar_asignacion_transporte_no_hace_commit(
    monkeypatch,
):
    session = SessionFake()
    db_fake = types.SimpleNamespace(session=session)
    monkeypatch.setitem(
        sys.modules,
        "app",
        types.SimpleNamespace(db=db_fake),
    )

    monkeypatch.setattr(
        selector,
        "correo_pp6040_habilitado",
        lambda: True,
    )
    monkeypatch.setattr(
        selector,
        "pedido_contiene_pp6040",
        lambda pedido: True,
    )
    monkeypatch.setattr(
        selector,
        "evaluar_decision_correo_pp6040",
        lambda pedido, preferencia_cliente="sucursal": {
            "decision": "sucursal",
            "motivo": "Sucursal/Punto Correo preferido",
            "sucursal": {
                "disponible": True,
                "precio": 13255.0,
                "servicio": "Correo Argentino Clasico",
            },
            "domicilio": {
                "disponible": True,
                "precio": 15957.0,
                "servicio": "Correo Argentino Clasico",
            },
        },
    )

    pedido = PedidoFake()

    resultado = (
        selector.preparar_asignacion_transporte_pedido(
            pedido,
        )
    )

    assert resultado.ok is True
    assert resultado.estado == "asignada"
    assert resultado.mensaje == (
        "Correo Argentino asignado (Sucursal)"
    )
    assert resultado.requiere_persistencia is True
    assert resultado.requiere_rollback is False
    assert pedido.empresa_envio == "Correo Argentino"
    assert pedido.tipo_entrega == "Sucursal"
    assert pedido.costo_envio == 13255.0
    assert pedido.costo_envio_sucursal == 13255.0
    assert pedido.costo_envio_domicilio == 15957.0
    assert session.committed is False
    assert session.rolled_back is False
