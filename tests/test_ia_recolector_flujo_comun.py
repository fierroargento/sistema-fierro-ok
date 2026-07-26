from types import SimpleNamespace

from services.ia_recolector_flujo_comun import (
    procesar_flujo_comun_recolector,
)


def ejecutar(
    *,
    texto="mensaje",
    forzar=False,
    hash_anterior="anterior",
    hash_actual="nuevo",
    resultado=None,
    orquestacion=None,
    error_orquestacion=None,
):
    pedido = SimpleNamespace(
        ia_ultimo_mensaje_hash=hash_anterior,
    )
    llamadas = []

    if resultado is None:
        resultado = {"ok": True}

    if orquestacion is None:
        orquestacion = SimpleNamespace(
            finalizada=False,
            respuesta_flujo=None,
        )

    def orquestar(*args, **kwargs):
        llamadas.append(("orquestar", args, kwargs))
        if error_orquestacion:
            raise error_orquestacion
        return orquestacion

    respuesta = procesar_flujo_comun_recolector(
        pedido=pedido,
        texto=texto,
        forzar=forzar,
        hash_texto_fn=lambda valor: hash_actual,
        datos_previos_fn=lambda *args, **kwargs: {
            "previo": True,
        },
        parece_nickname_fn=lambda valor: False,
        analizar_datos_fn=lambda *args: resultado,
        procesar_resultado_fn=lambda *args, **kwargs: (
            llamadas.append(
                ("procesar", args, kwargs)
            )
        ),
        iniciar_handoff_fn=lambda *args, **kwargs: None,
        orquestar_confirmacion_fn=orquestar,
        despacho_completo_fn=lambda pedido: True,
        actualizar_estado_fn=lambda *args, **kwargs: None,
        db_session=SimpleNamespace(),
        puede_enviar_fn=lambda *args, **kwargs: (True, ""),
        enviar_mensaje_fn=lambda *args, **kwargs: (True, ""),
        registrar_envio_fn=lambda *args, **kwargs: None,
        intentar_cross_sell_fn=lambda *args, **kwargs: None,
        es_afirmativo_fn=lambda texto: True,
        auto_responder_fn=lambda pedido: (
            llamadas.append(("auto", pedido))
        ),
        logger_fn=lambda mensaje: (
            llamadas.append(("log", mensaje))
        ),
    )

    return pedido, llamadas, respuesta


def test_texto_vacio_finaliza_sin_analizar():
    _, llamadas, respuesta = ejecutar(texto="")

    assert respuesta.finalizada is True
    assert respuesta.respuesta_analisis is None
    assert llamadas == []


def test_hash_repetido_finaliza_salvo_forzar():
    _, llamadas, respuesta = ejecutar(
        hash_anterior="igual",
        hash_actual="igual",
    )

    assert respuesta.finalizada is True
    assert respuesta.respuesta_analisis is None
    assert llamadas == []

    _, llamadas_forzado, respuesta_forzada = ejecutar(
        forzar=True,
        hash_anterior="igual",
        hash_actual="igual",
    )

    assert respuesta_forzada.finalizada is False
    assert any(
        llamada[0] == "procesar"
        for llamada in llamadas_forzado
    )


def test_procesa_orquesta_y_auto_responde():
    pedido, llamadas, respuesta = ejecutar()

    assert respuesta.finalizada is False
    assert respuesta.respuesta_analisis == {"ok": True}

    procesar = next(
        llamada
        for llamada in llamadas
        if llamada[0] == "procesar"
    )
    assert procesar[1][0] is pedido
    assert procesar[1][1] == "mensaje"
    assert procesar[2]["iniciar_handoff_fn"] is not None

    orquestar = next(
        llamada
        for llamada in llamadas
        if llamada[0] == "orquestar"
    )
    assert (
        orquestar[2]["wa_auto_iniciar_fn"]
        is procesar[2]["iniciar_handoff_fn"]
    )
    assert any(
        llamada[0] == "auto"
        for llamada in llamadas
    )


def test_confirmacion_finalizada_devuelve_respuesta():
    respuesta_flujo = {
        "ok": True,
        "estado": "sucursal_confirmada",
        "sucursal_confirmada": True,
    }

    _, llamadas, respuesta = ejecutar(
        orquestacion=SimpleNamespace(
            finalizada=True,
            respuesta_flujo=respuesta_flujo,
        ),
    )

    assert respuesta.finalizada is True
    assert respuesta.respuesta_analisis == respuesta_flujo
    assert not any(
        llamada[0] == "auto"
        for llamada in llamadas
    )


def test_error_de_orquestacion_conserva_resultado():
    _, llamadas, respuesta = ejecutar(
        error_orquestacion=RuntimeError("fallo"),
    )

    assert respuesta.finalizada is False
    assert respuesta.respuesta_analisis == {"ok": True}
    assert any(
        llamada[0] == "log"
        and "fallo" in llamada[1]
        for llamada in llamadas
    )
    assert any(
        llamada[0] == "auto"
        for llamada in llamadas
    )


def test_resultado_no_ok_no_auto_responde():
    _, llamadas, respuesta = ejecutar(
        resultado={"ok": False},
    )

    assert respuesta.respuesta_analisis == {
        "ok": False,
    }
    assert not any(
        llamada[0] == "auto"
        for llamada in llamadas
    )
