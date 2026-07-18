import sys
import types
from types import SimpleNamespace

from modules.transportes import selector
from modules.whatsapp import flows
from modules.whatsapp import flows_transporte
from modules.whatsapp.config import (
    WA_DESPACHO_EN_PROCESO,
    WA_FALTA_ELEGIR_TRANSPORTE,
)


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
        estado="Cargando",
        wa_estado="",
        wa_ultimo_contacto=None,
    )


def preparar_entorno(
    monkeypatch,
    session,
    enviados,
    escalados,
    *,
    oferta_ok,
):
    monkeypatch.setitem(
        sys.modules,
        "app",
        types.SimpleNamespace(
            db=types.SimpleNamespace(session=session),
        ),
    )

    monkeypatch.setattr(
        flows_transporte,
        "pedido_requiere_sucursal_via_cargo_pendiente",
        lambda pedido: False,
    )
    monkeypatch.setattr(
        flows_transporte,
        "actualizar_estado_conversacional_wa",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        flows_transporte,
        "registrar_evento_operativo_wa",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        flows_transporte,
        "wa_enviar_texto",
        lambda *args, **kwargs: (
            enviados.append((args, kwargs))
            or True
        ),
    )
    monkeypatch.setattr(
        flows,
        "_escalar_operador",
        lambda *args, **kwargs: (
            escalados.append((args, kwargs))
            or False
        ),
    )
    monkeypatch.setattr(
        selector,
        "pedido_contiene_pp6040",
        lambda pedido: True,
    )
    monkeypatch.setattr(
        selector,
        "preparar_asignacion_transporte_pedido",
        lambda pedido, preferencia_cliente="sucursal": (
            SimpleNamespace(
                ok=True,
                mensaje="Correo Argentino asignado (Sucursal)",
                requiere_rollback=False,
            )
        ),
    )

    def preparar_oferta(
        pedido,
        canal_origen="ml",
    ):
        if oferta_ok:
            pedido.wa_estado = WA_FALTA_ELEGIR_TRANSPORTE
            return SimpleNamespace(
                ok=True,
                mensaje="Elegí una sucursal Correo",
            )

        return SimpleNamespace(
            ok=False,
            mensaje="",
        )

    monkeypatch.setattr(
        selector,
        "preparar_oferta_sucursales_correo_pedido",
        preparar_oferta,
    )


def test_cierre_wa_persiste_asignacion_y_oferta_antes_de_enviar(
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
        oferta_ok=True,
    )
    pedido = pedido_fake()

    resultado = flows_transporte.wa_cerrar_datos_completos(
        pedido,
    )

    assert resultado is True
    assert session.commits == 1
    assert session.rollbacks == 0
    assert pedido.wa_estado == WA_FALTA_ELEGIR_TRANSPORTE
    assert len(enviados) == 1
    assert "Elegí una sucursal" in enviados[0][0][1]
    assert escalados == []


def test_cierre_wa_sin_oferta_persiste_asignacion_y_estado(
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
        oferta_ok=False,
    )
    pedido = pedido_fake()

    resultado = flows_transporte.wa_cerrar_datos_completos(
        pedido,
    )

    assert resultado is True
    assert session.commits == 1
    assert session.rollbacks == 0
    assert pedido.wa_estado == WA_DESPACHO_EN_PROCESO
    assert pedido.wa_ultimo_contacto is not None
    assert len(enviados) == 1
    assert escalados == []


def test_cierre_wa_no_confirma_si_falla_persistencia(
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
        oferta_ok=False,
    )
    pedido = pedido_fake()

    resultado = flows_transporte.wa_cerrar_datos_completos(
        pedido,
    )

    assert resultado is False
    assert session.commits == 1
    assert session.rollbacks == 1
    assert enviados == []
    assert len(escalados) == 1
    assert (
        "No se pudo guardar la asignación"
        in escalados[0][0][1]
    )
