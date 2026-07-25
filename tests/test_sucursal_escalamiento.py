from pathlib import Path
from types import SimpleNamespace

from services.workflow_sucursal_decision import (
    procesar_escalamiento_consulta_sucursal,
)


class SessionFake:
    def __init__(self, error=None):
        self.commits = 0
        self.error = error

    def commit(self):
        self.commits += 1
        if self.error:
            raise self.error


def crear_pedido(**cambios):
    datos = {
        "id": 15,
        "correo_sucursales_ofrecidas": None,
        "ia_sucursales_ofrecidas": None,
        "ml_mensajes_pendientes": False,
        "ia_requiere_operador": False,
        "ia_resumen": "",
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def procesar(
    pedido,
    texto,
    *,
    confirmacion=None,
    consulta=False,
    session=None,
    logs=None,
):
    return procesar_escalamiento_consulta_sucursal(
        pedido,
        texto,
        confirmacion,
        pedido_es_plegable_fn=lambda _pedido: False,
        es_consulta_no_eleccion_fn=(
            lambda _texto: consulta
        ),
        db_session=session or SessionFake(),
        logger_fn=(
            logs.append
            if logs is not None
            else None
        ),
    )


def test_sin_opciones_ofrecidas_no_escala():
    pedido = crear_pedido()
    session = SessionFake()

    resultado = procesar(
        pedido,
        "¿Dónde queda?",
        consulta=True,
        session=session,
    )

    assert resultado.deteccion.puede_detectar is False
    assert resultado.escalada is False
    assert resultado.finalizar_analisis is False
    assert session.commits == 0
    assert pedido.ia_requiere_operador is False


def test_correo_ofrecido_no_usa_escalamiento_via_cargo():
    pedido = crear_pedido(
        correo_sucursales_ofrecidas='["CA-1"]',
    )
    session = SessionFake()

    resultado = procesar(
        pedido,
        "¿Qué horario tiene?",
        consulta=True,
        session=session,
    )

    assert resultado.deteccion.correo_ofrecidas is True
    assert resultado.deteccion.via_cargo_ofrecidas is False
    assert resultado.escalada is False
    assert session.commits == 0


def test_consulta_via_cargo_marca_y_persiste():
    pedido = crear_pedido(
        ia_sucursales_ofrecidas='["VC-1"]',
        ia_resumen="Datos recibidos",
    )
    session = SessionFake()

    resultado = procesar(
        pedido,
        "¿Dónde queda la sucursal?",
        consulta=True,
        session=session,
    )

    assert resultado.escalada is True
    assert resultado.finalizar_analisis is True
    assert resultado.error == ""
    assert pedido.ml_mensajes_pendientes is True
    assert pedido.ia_requiere_operador is True
    assert (
        "Cliente consultó sobre sucursal"
        in pedido.ia_resumen
    )
    assert session.commits == 1


def test_confirmacion_requiere_operador_tambien_escala():
    pedido = crear_pedido(
        ia_sucursales_ofrecidas='["VC-1"]',
    )
    session = SessionFake()
    confirmacion = SimpleNamespace(
        requiere_operador=True,
    )

    resultado = procesar(
        pedido,
        "mensaje mixto",
        confirmacion=confirmacion,
        consulta=False,
        session=session,
    )

    assert resultado.escalada is True
    assert resultado.finalizar_analisis is True
    assert session.commits == 1


def test_error_de_commit_conserva_finalizacion_legacy():
    pedido = crear_pedido(
        ia_sucursales_ofrecidas='["VC-1"]',
    )
    session = SessionFake(
        RuntimeError("fallo simulado"),
    )
    logs = []

    resultado = procesar(
        pedido,
        "¿Abren hoy?",
        consulta=True,
        session=session,
        logs=logs,
    )

    assert resultado.escalada is True
    assert resultado.finalizar_analisis is True
    assert resultado.error == "fallo simulado"
    assert pedido.ia_requiere_operador is True
    assert session.commits == 1
    assert any(
        "fallo simulado" in mensaje
        for mensaje in logs
    )


def test_servicio_no_depende_de_app_ni_flask():
    texto = Path(
        "services/workflow_sucursal_decision.py"
    ).read_text(encoding="utf-8-sig")

    assert "from app import" not in texto
    assert "import app" not in texto
    assert "from flask import" not in texto
