from types import SimpleNamespace

from services.ia_auto_respuesta_logistica import (
    procesar_asignacion_transporte_pp6040,
)


class SessionFake:
    def __init__(self):
        self.eventos = []

    def commit(self):
        self.eventos.append("commit")

    def rollback(self):
        self.eventos.append("rollback")


def ejecutar(
    pedido,
    resultado,
    *,
    plegable=True,
    session=None,
    preparar_fn=None,
    logs=None,
):
    session = session or SessionFake()
    logs = logs if logs is not None else []

    if preparar_fn is None:
        preparar_fn = lambda _pedido: resultado

    respuesta = procesar_asignacion_transporte_pp6040(
        pedido,
        pedido_es_plegable_fn=(
            lambda _pedido: plegable
        ),
        preparar_asignacion_fn=preparar_fn,
        construir_marca_revision_fn=(
            lambda cp, motivo: f"REVISION:{cp}:{motivo}"
        ),
        agregar_marca_resumen_fn=(
            lambda resumen, marca, limite=1000:
            f"{resumen} | {marca}".strip(" |")[:limite]
        ),
        db_session=session,
        log_fn=logs.append,
    )

    return respuesta, session, logs


def test_no_plegable_no_prepara_ni_persiste():
    pedido = SimpleNamespace(id=1)
    llamados = []

    respuesta, session, _logs = ejecutar(
        pedido,
        None,
        plegable=False,
        preparar_fn=lambda _pedido: llamados.append(True),
    )

    assert respuesta.procesada is False
    assert respuesta.transporte_asignado is False
    assert respuesta.motivo == "no_aplicable"
    assert llamados == []
    assert session.eventos == []


def test_asignacion_exitosa_actualiza_resumen_y_commit():
    pedido = SimpleNamespace(
        id=20,
        ia_resumen="Datos completos",
    )
    resultado = SimpleNamespace(
        ok=True,
        mensaje="Correo Argentino asignado",
        requiere_rollback=False,
    )

    respuesta, session, logs = ejecutar(
        pedido,
        resultado,
    )

    assert respuesta.procesada is True
    assert respuesta.transporte_asignado is True
    assert respuesta.motivo == "transporte_asignado"
    assert pedido.ia_resumen == (
        "Datos completos | Correo Argentino asignado"
    )
    assert session.eventos == ["commit"]
    assert logs == [
        "[TRANSPORTES] Pedido #20: "
        "Correo Argentino asignado"
    ]


def test_rollback_requerido_ocurre_antes_del_commit():
    pedido = SimpleNamespace(
        id=21,
        ia_resumen="",
    )
    resultado = SimpleNamespace(
        ok=True,
        mensaje="Correo asignado",
        requiere_rollback=True,
    )

    respuesta, session, _logs = ejecutar(
        pedido,
        resultado,
    )

    assert respuesta.transporte_asignado is True
    assert session.eventos == ["rollback", "commit"]


def test_resultado_fallido_marca_revision_operador():
    pedido = SimpleNamespace(
        id=22,
        codigo_postal="7600",
        ia_resumen="Datos completos",
        ml_mensajes_pendientes=False,
        ia_requiere_operador=False,
    )
    resultado = SimpleNamespace(
        ok=False,
        mensaje="Sin cobertura",
        requiere_rollback=False,
    )

    respuesta, session, _logs = ejecutar(
        pedido,
        resultado,
    )

    assert respuesta.procesada is True
    assert respuesta.transporte_asignado is False
    assert respuesta.motivo == "datos_completos"
    assert pedido.ml_mensajes_pendientes is True
    assert pedido.ia_requiere_operador is True
    assert pedido.ia_resumen == (
        "Datos completos | REVISION:7600:Sin cobertura"
    )
    assert session.eventos == ["commit"]


def test_excepcion_hace_rollback_y_finaliza_seguro():
    pedido = SimpleNamespace(id=23)

    def preparar_con_error(_pedido):
        raise RuntimeError("fallo externo")

    respuesta, session, logs = ejecutar(
        pedido,
        None,
        preparar_fn=preparar_con_error,
    )

    assert respuesta.procesada is True
    assert respuesta.transporte_asignado is False
    assert respuesta.motivo == "datos_completos"
    assert session.eventos == ["rollback"]
    assert logs == [
        "[TRANSPORTES] Error asignando transporte "
        "pedido #23: fallo externo"
    ]
