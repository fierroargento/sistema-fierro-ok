import json
import sys
import types

from modules.transportes import selector


class SessionFake:
    def __init__(self):
        self.committed = False

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


class PedidoFake:
    def __init__(self):
        self.ia_requiere_operador = False
        self.ml_mensajes_pendientes = False
        self.wa_estado = ""
        self.ia_resumen = ""
        self.empresa_envio = ""
        self.tipo_entrega = ""
        self.correo_sucursales_ofrecidas = ""
        self.ia_sucursales_ofrecidas = ""


def test_preparar_sucursales_correo_respeta_cantidad_sin_persistir(monkeypatch):
    session = SessionFake()
    db_fake = types.SimpleNamespace(session=session)
    monkeypatch.setitem(sys.modules, "app", types.SimpleNamespace(db=db_fake))

    monkeypatch.setattr(selector, "correo_pp6040_habilitado", lambda: True)

    monkeypatch.setattr(
        "services.correo_argentino_operacion.obtener_preferencias_operativas_correo",
        lambda: {
            "cantidad_sucursales_cliente": 2,
        },
    )

    monkeypatch.setattr(
        selector,
        "obtener_sucursales_correo_por_pedido",
        lambda pedido: [
            {"id": "R0100", "nombre": "Sucursal 1", "direccion": "Calle 1", "localidad": "Bariloche"},
            {"id": "R0101", "nombre": "Sucursal 2", "direccion": "Calle 2", "localidad": "Bariloche"},
            {"id": "R0102", "nombre": "Sucursal 3", "direccion": "Calle 3", "localidad": "Bariloche"},
        ],
    )

    pedido = PedidoFake()

    resultado = selector.preparar_oferta_sucursales_correo_pedido(pedido)
    mensaje = resultado.mensaje

    assert mensaje is not None
    assert "Sucursal 1" in mensaje
    assert "Sucursal 2" in mensaje
    assert "Sucursal 3" not in mensaje

    guardadas = json.loads(pedido.correo_sucursales_ofrecidas)
    assert len(guardadas) == 2
    assert pedido.empresa_envio == "Correo Argentino"
    assert pedido.tipo_entrega == "Sucursal"
    assert session.committed is False
