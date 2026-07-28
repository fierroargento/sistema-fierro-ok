from pathlib import Path
from types import SimpleNamespace

from services.ia_auto_respuesta_logistica import (
    ResultadoAsignacionTransporteAutoRespuesta,
    aplicar_default_via_cargo_auto_respuesta,
    procesar_asignacion_transporte_pp6040,
    procesar_datos_completos_auto_respuesta_ml,
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


def test_orquestador_delega_persistencia_del_default_via_cargo():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )
    servicio = Path(
        "services/ia_auto_respuesta_logistica.py"
    ).read_text(encoding="utf-8-sig")

    inicio_app = app.index(
        "def ia_auto_responder_post_analisis("
    )
    fin_app = app.find(
        "\ndef ",
        inicio_app + 1,
    )
    if fin_app == -1:
        fin_app = len(app)

    bloque_app = app[inicio_app:fin_app]

    assert (
        "procesar_datos_completos_auto_respuesta_ml("
        in bloque_app
    )
    assert (
        "aplicar_default_via_cargo_auto_respuesta("
        not in bloque_app
    )

    assert (
        "def procesar_datos_completos_auto_respuesta_ml("
        in servicio
    )
    assert (
        "aplicar_default_service_fn("
        in servicio
    )
    assert (
        "aplicar_default_via_cargo_auto_respuesta"
        in servicio
    )
    assert (
        "aplicar_default_fn=aplicar_default_fn"
        in servicio
    )

    assert "db.session.commit()" not in bloque_app
    assert "db.session.rollback()" not in bloque_app
    assert "[LOGISTICA-DEFAULTS]" not in bloque_app

def ejecutar_datos_completos(
    *,
    es_via_cargo=False,
    asignado=True,
    motivo_asignacion="transporte_asignado",
    resultado_sucursales=None,
    ok_wa=False,
    motivo_wa="datos_completos",
):
    pedido = SimpleNamespace(id=40)
    session = SessionFake()
    eventos = []

    def procesar_asignacion_fake(
        _pedido,
        **_kwargs,
    ):
        eventos.append("asignacion")
        return ResultadoAsignacionTransporteAutoRespuesta(
            procesada=True,
            transporte_asignado=asignado,
            motivo=motivo_asignacion,
        )

    def aplicar_default_fake(
        _pedido,
        **_kwargs,
    ):
        eventos.append("default")
        return True

    def enviar_sugerencia_fake(**_kwargs):
        eventos.append("sugerencias")
        return resultado_sucursales

    def iniciar_wa_fake(
        _pedido,
        *,
        faltantes,
        motivo,
    ):
        eventos.append(
            ("wa", faltantes, motivo)
        )
        return ok_wa, motivo_wa

    resultado = procesar_datos_completos_auto_respuesta_ml(
        pedido,
        es_ml_acordas_fn=lambda _pedido: True,
        pedido_es_plegable_fn=(
            lambda _pedido: not es_via_cargo
        ),
        preparar_asignacion_fn=lambda _pedido: None,
        construir_marca_revision_fn=(
            lambda _cp, _motivo: ""
        ),
        agregar_marca_resumen_fn=(
            lambda resumen, _marca, limite=1000:
            resumen[:limite]
        ),
        aplicar_default_fn=lambda _pedido: True,
        sugerir_sucursales_fn=lambda _pedido: "",
        puede_enviar_mensaje_fn=lambda **_kwargs: (
            True,
            "permitido",
        ),
        enviar_mensaje_ml_fn=lambda *_args, **_kwargs: None,
        registrar_envio_automatico_fn=(
            lambda **_kwargs: None
        ),
        ia_hash_texto_fn=lambda texto: texto,
        wa_auto_iniciar_fn=iniciar_wa_fake,
        db_session=session,
        now_fn=lambda: None,
        log_fn=lambda _mensaje: None,
        procesar_asignacion_service_fn=(
            procesar_asignacion_fake
        ),
        aplicar_default_service_fn=(
            aplicar_default_fake
        ),
        enviar_sugerencia_service_fn=(
            enviar_sugerencia_fake
        ),
    )

    return resultado, eventos


def test_datos_completos_pp6040_fallido_finaliza():
    resultado, eventos = ejecutar_datos_completos(
        asignado=False,
        motivo_asignacion="datos_completos",
    )

    assert resultado.ok is False
    assert resultado.motivo == "datos_completos"
    assert eventos == ["asignacion"]


def test_datos_completos_pp6040_asignado_salta_default():
    resultado, eventos = ejecutar_datos_completos(
        asignado=True,
        resultado_sucursales={
            "ok": True,
            "motivo": "sucursales_enviadas",
        },
    )

    assert resultado.ok is True
    assert resultado.motivo == "sucursales_enviadas"
    assert eventos == [
        "asignacion",
        "sugerencias",
    ]


def test_datos_completos_via_cargo_aplica_default():
    resultado, eventos = ejecutar_datos_completos(
        es_via_cargo=True,
        resultado_sucursales=None,
        ok_wa=True,
    )

    assert resultado.ok is True
    assert resultado.motivo == (
        "wa_iniciado_datos_completos"
    )
    assert eventos[0:2] == [
        "default",
        "sugerencias",
    ]
    assert eventos[2] == (
        "wa",
        [],
        (
            "ia_auto_responder_post_analisis_"
            "datos_completos"
        ),
    )


def test_datos_completos_conserva_error_sucursales():
    resultado, eventos = ejecutar_datos_completos(
        es_via_cargo=True,
        resultado_sucursales={
            "ok": False,
            "motivo": "error_sucursales",
        },
    )

    assert resultado.ok is False
    assert resultado.motivo == "error_sucursales"
    assert eventos == [
        "default",
        "sugerencias",
    ]


def test_datos_completos_conserva_motivo_wa():
    resultado, eventos = ejecutar_datos_completos(
        es_via_cargo=True,
        resultado_sucursales=None,
        ok_wa=False,
        motivo_wa="ml_debe_cerrar_sucursal",
    )

    assert resultado.ok is False
    assert resultado.motivo == (
        "ml_debe_cerrar_sucursal"
    )
    assert eventos[-1][0] == "wa"


def test_app_delega_flujo_de_datos_completos():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )
    inicio = app.index(
        "def ia_auto_responder_post_analisis("
    )
    fin = app.find(
        "\ndef ",
        inicio + 1,
    )
    if fin == -1:
        fin = len(app)

    bloque = app[inicio:fin]

    assert (
        "procesar_datos_completos_auto_respuesta_ml("
        in bloque
    )
    assert (
        "resultado_datos_completos.motivo"
        in bloque
    )

    prohibidos = [
        "pp6040_transporte_asignado = False",
        "resultado_asignacion_pp6040",
        "resultado_sucursales =",
        'motivo="ia_auto_responder_post_analisis_'
        'datos_completos"',
        'return True, "wa_iniciado_datos_completos"',
    ]

    for prohibido in prohibidos:
        assert prohibido not in bloque
