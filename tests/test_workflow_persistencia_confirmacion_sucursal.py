from pathlib import Path
from types import SimpleNamespace

from services.workflow_persistencia_confirmacion_sucursal import (
    ejecutar_estado_y_persistencia_post_confirmacion,
)


class SesionFake:
    def __init__(
        self,
        *,
        error_commit=None,
        error_rollback=None,
        llamadas=None,
    ):
        self.error_commit = error_commit
        self.error_rollback = error_rollback
        self.llamadas = llamadas if llamadas is not None else []

    def commit(self):
        self.llamadas.append("commit")
        if self.error_commit:
            raise self.error_commit

    def rollback(self):
        self.llamadas.append("rollback")
        if self.error_rollback:
            raise self.error_rollback


def plan_fake(**cambios):
    datos = {
        "confirmada": True,
        "actualizar_estado": True,
        "persistir": True,
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def test_actualiza_estado_y_luego_persiste():
    llamadas = []
    pedido = SimpleNamespace(id=10)
    sesion = SesionFake(llamadas=llamadas)

    def actualizar(valor):
        assert valor is pedido
        llamadas.append("actualizar")

    resultado = (
        ejecutar_estado_y_persistencia_post_confirmacion(
            pedido=pedido,
            plan=plan_fake(),
            actualizar_estado_fn=actualizar,
            db_session=sesion,
            log_fn=lambda _mensaje: None,
        )
    )

    assert llamadas == [
        "actualizar",
        "commit",
    ]
    assert resultado.exitosa is True
    assert resultado.estado == "persistida"
    assert resultado.estado_actualizado is True
    assert resultado.persistencia_realizada is True
    assert resultado.motivo == ""


def test_error_actualizando_estado_no_impide_commit():
    logs = []
    sesion = SesionFake()

    def actualizar_error(_pedido):
        raise RuntimeError("fallo estado")

    resultado = (
        ejecutar_estado_y_persistencia_post_confirmacion(
            pedido=SimpleNamespace(id=10),
            plan=plan_fake(),
            actualizar_estado_fn=actualizar_error,
            db_session=sesion,
            log_fn=logs.append,
        )
    )

    assert sesion.llamadas == ["commit"]
    assert resultado.exitosa is True
    assert resultado.estado == "persistida"
    assert resultado.estado_actualizado is False
    assert resultado.persistencia_realizada is True
    assert (
        resultado.motivo
        == "error_actualizando_estado:fallo estado"
    )
    assert len(logs) == 1
    assert "autoactualizar estado" in logs[0]


def test_error_de_commit_hace_rollback_y_no_es_exitoso():
    logs = []
    sesion = SesionFake(
        error_commit=RuntimeError("fallo commit"),
    )

    resultado = (
        ejecutar_estado_y_persistencia_post_confirmacion(
            pedido=SimpleNamespace(id=10),
            plan=plan_fake(),
            actualizar_estado_fn=lambda _pedido: None,
            db_session=sesion,
            log_fn=logs.append,
        )
    )

    assert sesion.llamadas == [
        "commit",
        "rollback",
    ]
    assert resultado.exitosa is False
    assert resultado.estado == "error_persistencia"
    assert resultado.persistencia_realizada is False
    assert resultado.motivo == "fallo commit"
    assert any(
        "No se pudo persistir" in mensaje
        for mensaje in logs
    )


def test_error_de_rollback_no_oculta_error_de_commit():
    logs = []
    sesion = SesionFake(
        error_commit=RuntimeError("fallo commit"),
        error_rollback=RuntimeError("fallo rollback"),
    )

    resultado = (
        ejecutar_estado_y_persistencia_post_confirmacion(
            pedido=SimpleNamespace(id=10),
            plan=plan_fake(),
            actualizar_estado_fn=lambda _pedido: None,
            db_session=sesion,
            log_fn=logs.append,
        )
    )

    assert resultado.estado == "error_persistencia"
    assert resultado.motivo == "fallo commit"
    assert sesion.llamadas == [
        "commit",
        "rollback",
    ]
    assert any(
        "Error haciendo rollback" in mensaje
        for mensaje in logs
    )


def test_plan_sin_persistencia_solo_actualiza_estado():
    llamadas = []
    sesion = SesionFake(llamadas=llamadas)

    resultado = (
        ejecutar_estado_y_persistencia_post_confirmacion(
            pedido=SimpleNamespace(id=10),
            plan=plan_fake(persistir=False),
            actualizar_estado_fn=(
                lambda _pedido: (
                    llamadas.append("actualizar")
                )
            ),
            db_session=sesion,
            log_fn=lambda _mensaje: None,
        )
    )

    assert llamadas == ["actualizar"]
    assert resultado.exitosa is True
    assert (
        resultado.estado
        == "aplicada_sin_persistencia"
    )
    assert resultado.persistencia_realizada is False


def test_plan_sin_confirmacion_no_hace_nada():
    llamadas = []
    sesion = SesionFake(llamadas=llamadas)

    resultado = (
        ejecutar_estado_y_persistencia_post_confirmacion(
            pedido=SimpleNamespace(id=10),
            plan=plan_fake(confirmada=False),
            actualizar_estado_fn=(
                lambda _pedido: (
                    llamadas.append("actualizar")
                )
            ),
            db_session=sesion,
        )
    )

    assert resultado.estado == "no_aplica"
    assert resultado.exitosa is False
    assert llamadas == []


def test_servicio_no_envia_mensajes_ni_hace_cross_sell():
    texto = Path(
        "services/"
        "workflow_persistencia_confirmacion_sucursal.py"
    ).read_text(encoding="utf-8")

    prohibidos = [
        "from app import",
        "ml_enviar",
        "wa_enviar",
        "registrar_envio_automatico",
        "intentar_wa_cross_sell",
    ]

    for prohibido in prohibidos:
        assert prohibido not in texto
