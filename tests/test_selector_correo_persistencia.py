from pathlib import Path
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




class SessionExitosa:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class PedidoFake:
    def __init__(self):
        self.oferta_aplicada = False


def test_marcar_escalado_hace_rollback_si_falla_persistencia(
    monkeypatch,
):
    session = SessionCommitFallido()
    monkeypatch.setattr(
        selector,
        "db",
        SimpleNamespace(session=session),
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

def test_marcar_escalado_persiste_banderas_y_motivo(
    monkeypatch,
):
    session = SessionExitosa()
    monkeypatch.setattr(
        selector,
        "db",
        SimpleNamespace(session=session),
    )

    pedido = SimpleNamespace(
        ia_requiere_operador=False,
        ml_mensajes_pendientes=False,
        wa_estado="",
        ia_resumen="Resumen anterior",
    )

    selector._marcar_escalado(
        pedido,
        "Revisión manual de transporte",
    )

    assert pedido.ia_requiere_operador is True
    assert pedido.ml_mensajes_pendientes is True
    assert pedido.wa_estado == "requiere_operador"
    assert pedido.ia_resumen == (
        "Resumen anterior | TRANSPORTE: "
        "Revisión manual de transporte"
    )
    assert session.commits == 1
    assert session.rollbacks == 0


def test_selector_usa_extension_canonica_db():
    texto = Path(
        "modules/transportes/selector.py"
    ).read_text(encoding="utf-8-sig")

    assert texto.count("from extensions import db") == 1
    assert "from app import db" not in texto
    assert texto.count("db.session.commit()") == 1
    assert texto.count("db.session.rollback()") == 1
