from pathlib import Path
from types import SimpleNamespace

from services.ia_auto_respuesta_logistica import (
    aplicar_default_via_cargo_auto_respuesta,
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


def test_default_via_cargo_modificado_hace_commit():
    pedido = SimpleNamespace(id=30)
    session = SessionFake()
    llamados = []

    modificado = aplicar_default_via_cargo_auto_respuesta(
        pedido,
        aplicar_default_fn=(
            lambda recibido:
            llamados.append(recibido) or True
        ),
        db_session=session,
    )

    assert modificado is True
    assert llamados == [pedido]
    assert session.eventos == ["commit"]


def test_default_via_cargo_sin_cambios_no_persiste():
    pedido = SimpleNamespace(id=31)
    session = SessionFake()

    modificado = aplicar_default_via_cargo_auto_respuesta(
        pedido,
        aplicar_default_fn=lambda _pedido: False,
        db_session=session,
    )

    assert modificado is False
    assert session.eventos == []


def test_default_via_cargo_con_error_hace_rollback():
    pedido = SimpleNamespace(id=32)
    session = SessionFake()
    logs = []

    def aplicar_con_error(_pedido):
        raise RuntimeError("cotizador caído")

    modificado = aplicar_default_via_cargo_auto_respuesta(
        pedido,
        aplicar_default_fn=aplicar_con_error,
        db_session=session,
        log_fn=logs.append,
    )

    assert modificado is False
    assert session.eventos == ["rollback"]
    assert logs == [
        "[LOGISTICA-DEFAULTS] No se pudo aplicar "
        "default Via Cargo pedido #32: cotizador caído"
    ]


def test_app_delega_persistencia_del_default_via_cargo():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )
    inicio = app.index(
        "def ia_auto_responder_post_analisis"
    )
    fin = app.find(
        "\ndef ",
        inicio + 1,
    )
    if fin == -1:
        fin = len(app)
    bloque = app[inicio:fin]

    assert (
        "aplicar_default_via_cargo_auto_respuesta("
        in bloque
    )
    assert (
        "aplicar_default_fn=("
        in bloque
    )
    assert (
        "aplicar_default_via_cargo_sucursal_ml_acordas"
        in bloque
    )

    assert "db.session.commit()" not in bloque
    assert "db.session.rollback()" not in bloque
    assert "[LOGISTICA-DEFAULTS]" not in bloque
