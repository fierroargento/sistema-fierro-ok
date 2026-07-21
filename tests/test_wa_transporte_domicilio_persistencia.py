import sys
import types
from types import SimpleNamespace

from modules.transportes import selector
from modules.whatsapp import flows
from modules.whatsapp import flows_transporte
from modules.whatsapp.config import WA_DESPACHO_EN_PROCESO


class SessionFake:
    def __init__(self, fallar_commit=False):
        self.fallar_commit = fallar_commit
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1
        if self.fallar_commit:
            raise RuntimeError(
                "fallo simulado de persistencia"
            )

    def rollback(self):
        self.rollbacks += 1


def pedido_fake():
    return SimpleNamespace(
        telefono="5491157347193",
        cliente="Cliente",
        id=1,
        id_venta="ML1",
        wa_estado="falta_elegir_transporte",
        wa_ultimo_contacto=None,
    )


def preparar_entorno(
    monkeypatch,
    session,
    enviados,
    escalados,
):
    monkeypatch.setitem(
        sys.modules,
        "app",
        types.SimpleNamespace(
            aplicar_default_tipo_entrega=(
                lambda pedido: False
            ),
        ),
    )
    monkeypatch.setattr(
        flows_transporte,
        "db",
        types.SimpleNamespace(session=session),
    )

    monkeypatch.setattr(
        flows_transporte,
        "pedido_requiere_sucursal_via_cargo_pendiente",
        lambda pedido: False,
    )
    monkeypatch.setattr(
        flows_transporte,
        "wa_enviar_texto",
        lambda *args, **kwargs: enviados.append(
            (args, kwargs)
        ),
    )
    monkeypatch.setattr(
        flows,
        "_es_consulta_factura",
        lambda texto: False,
    )
    monkeypatch.setattr(
        flows,
        "_escalar_operador",
        lambda *args, **kwargs: escalados.append(
            (args, kwargs)
        ),
    )
    monkeypatch.setattr(
        selector,
        "preparar_asignacion_transporte_pedido",
        lambda pedido, preferencia_cliente="sucursal": (
            SimpleNamespace(
                ok=True,
                mensaje="Correo domicilio asignado",
                requiere_rollback=False,
            )
        ),
    )


def test_wa_domicilio_persiste_antes_de_enviar(
    monkeypatch,
):
    session = SessionFake()
    enviados = []
    escalados = []
    preparar_entorno(
        monkeypatch,
        session,
        enviados,
        escalados,
    )
    pedido = pedido_fake()

    resultado = (
        flows_transporte.wa_procesar_eleccion_transporte(
            pedido,
            "quiero entrega en casa",
        )
    )

    assert resultado is None
    assert session.commits == 1
    assert session.rollbacks == 0
    assert pedido.wa_estado == WA_DESPACHO_EN_PROCESO
    assert pedido.wa_ultimo_contacto is not None
    assert len(enviados) == 1
    assert escalados == []


def test_wa_domicilio_no_confirma_si_falla_persistencia(
    monkeypatch,
):
    session = SessionFake(fallar_commit=True)
    enviados = []
    escalados = []
    preparar_entorno(
        monkeypatch,
        session,
        enviados,
        escalados,
    )
    pedido = pedido_fake()

    resultado = (
        flows_transporte.wa_procesar_eleccion_transporte(
            pedido,
            "quiero entrega en casa",
        )
    )

    assert resultado is None
    assert session.commits == 1
    assert session.rollbacks == 1
    assert enviados == []
    assert len(escalados) == 1
    assert (
        "No se pudo guardar la asignación"
        in escalados[0][0][1]
    )
