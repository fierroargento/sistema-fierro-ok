from types import SimpleNamespace

from services.ia_recolector_flujo_cp import (
    procesar_flujo_codigo_postal_recolector,
)


def ejecutar(
    *,
    cp="2761",
    post_finaliza=False,
    escalamiento_finaliza=False,
    puede_detectar=False,
    correo_ofrecidas=False,
    aplicacion=True,
    respuesta_notificacion=None,
):
    pedido = SimpleNamespace(
        ia_faltantes=["codigo_postal"],
        codigo_postal="",
    )
    llamadas = []

    confirmacion = SimpleNamespace(
        confirmada=False,
    )
    deteccion = SimpleNamespace(
        puede_detectar=puede_detectar,
        correo_ofrecidas=correo_ofrecidas,
    )

    resultado = (
        procesar_flujo_codigo_postal_recolector(
            pedido=pedido,
            texto="CP 2761",
            texto_ultimo="2761",
            faltantes_fn=lambda pedido: [
                "codigo_postal",
            ],
            resolver_cp_fn=lambda *args, **kwargs: cp,
            aplicar_cp_fn=lambda *args, **kwargs: (
                llamadas.append(("aplicar_cp", args, kwargs))
            ),
            normalizar_ubicacion_fn=lambda *args, **kwargs: None,
            procesar_post_cp_fn=lambda *args, **kwargs: (
                SimpleNamespace(
                    confirmacion=confirmacion,
                    finalizar_analisis=post_finaliza,
                )
            ),
            orquestar_confirmacion_temprana_fn=(
                lambda *args, **kwargs: None
            ),
            despacho_completo_fn=lambda pedido: True,
            actualizar_estado_fn=lambda *args, **kwargs: None,
            es_afirmativo_fn=lambda texto: True,
            auto_responder_fn=lambda pedido: None,
            procesar_escalamiento_fn=(
                lambda *args, **kwargs: SimpleNamespace(
                    deteccion=deteccion,
                    finalizar_analisis=(
                        escalamiento_finaliza
                    ),
                )
            ),
            pedido_es_plegable_fn=lambda pedido: False,
            es_consulta_no_eleccion_fn=lambda texto: False,
            detectar_sucursal_fn=lambda *args: (
                llamadas.append(("detectar", args))
                or {"id": "sucursal"}
            ),
            aplicar_sucursal_fn=lambda *args, **kwargs: (
                llamadas.append(
                    ("aplicar_sucursal", args, kwargs)
                )
                or SimpleNamespace(
                    aplicada=aplicacion,
                )
            ),
            notificar_sucursal_fn=lambda *args, **kwargs: (
                llamadas.append(
                    ("notificar", args, kwargs)
                )
                or SimpleNamespace(
                    respuesta_flujo=(
                        respuesta_notificacion
                    ),
                )
            ),
            puede_enviar_fn=lambda *args, **kwargs: (True, ""),
            enviar_mensaje_fn=lambda *args, **kwargs: (True, ""),
            registrar_envio_fn=lambda *args, **kwargs: None,
            wa_auto_iniciar_fn=lambda *args, **kwargs: None,
            db_session=SimpleNamespace(),
            logger_fn=lambda mensaje: None,
        )
    )

    return pedido, llamadas, resultado


def test_sin_codigo_postal_no_ejecuta_rama():
    _, llamadas, resultado = ejecutar(cp="")

    assert resultado.cp_detectado == ""
    assert resultado.finalizar_analisis is False
    assert resultado.respuesta_analisis is None
    assert llamadas == []


def test_codigo_postal_se_aplica():
    _, llamadas, resultado = ejecutar()

    assert resultado.cp_detectado == "2761"
    assert any(
        llamada[0] == "aplicar_cp"
        for llamada in llamadas
    )


def test_confirmacion_temprana_finaliza_con_respuesta():
    _, llamadas, resultado = ejecutar(
        post_finaliza=True,
    )

    assert resultado.finalizar_analisis is True
    assert resultado.respuesta_analisis == {
        "ok": True,
        "estado": "sucursal_confirmada",
        "sucursal_confirmada": True,
    }
    assert not any(
        llamada[0] == "aplicar_sucursal"
        for llamada in llamadas
    )


def test_escalamiento_finaliza_sin_respuesta():
    _, llamadas, resultado = ejecutar(
        escalamiento_finaliza=True,
    )

    assert resultado.finalizar_analisis is True
    assert resultado.respuesta_analisis is None
    assert not any(
        llamada[0] == "aplicar_sucursal"
        for llamada in llamadas
    )


def test_sucursal_detectada_se_aplica_y_notifica():
    respuesta = (False, "repetido")

    _, llamadas, resultado = ejecutar(
        puede_detectar=True,
        correo_ofrecidas=True,
        respuesta_notificacion=respuesta,
    )

    nombres = [
        llamada[0]
        for llamada in llamadas
    ]

    assert nombres == [
        "aplicar_cp",
        "detectar",
        "aplicar_sucursal",
        "notificar",
    ]
    assert resultado.finalizar_analisis is True
    assert resultado.respuesta_analisis == respuesta


def test_sin_sucursal_aplicada_continua_flujo():
    _, llamadas, resultado = ejecutar(
        puede_detectar=True,
        correo_ofrecidas=True,
        aplicacion=False,
    )

    assert resultado.finalizar_analisis is False
    assert not any(
        llamada[0] == "notificar"
        for llamada in llamadas
    )


def test_notificacion_sin_respuesta_continua_flujo():
    _, llamadas, resultado = ejecutar(
        puede_detectar=True,
        correo_ofrecidas=True,
        respuesta_notificacion=None,
    )

    assert any(
        llamada[0] == "notificar"
        for llamada in llamadas
    )
    assert resultado.finalizar_analisis is False
    assert resultado.respuesta_analisis is None
