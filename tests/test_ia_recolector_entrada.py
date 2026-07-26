from types import SimpleNamespace

from services.ia_recolector_entrada import (
    preparar_entrada_recolector_ml,
)


def ejecutar(
    *,
    pedido=None,
    aplica=True,
    mensaje=True,
    texto="mensaje",
    seller_id="seller-2",
):
    if pedido is None:
        pedido = SimpleNamespace(
            contacto_iniciado=True,
        )

    llamadas = []

    mensaje_preparado = (
        SimpleNamespace(
            ultimo={"id": "m1"},
            texto_ultimo="último",
            texto=texto,
        )
        if mensaje
        else None
    )

    resultado = preparar_entrada_recolector_ml(
        pedido=pedido,
        mensajes=[{"id": "m1"}],
        seller_id=seller_id,
        es_pedido_aplicable_fn=lambda valor: aplica,
        preparar_mensaje_fn=lambda *args, **kwargs: (
            llamadas.append(
                ("preparar", args, kwargs)
            )
            or mensaje_preparado
        ),
        marcar_respuesta_fn=lambda *args, **kwargs: (
            llamadas.append(
                ("marcar", args, kwargs)
            )
        ),
    )

    return pedido, llamadas, resultado


def test_sin_pedido_no_prepara():
    llamadas = []

    resultado = preparar_entrada_recolector_ml(
        pedido=None,
        mensajes=[],
        es_pedido_aplicable_fn=lambda pedido: True,
        preparar_mensaje_fn=lambda *args, **kwargs: (
            llamadas.append("preparar")
        ),
        marcar_respuesta_fn=lambda *args, **kwargs: None,
    )

    assert resultado.habilitada is False
    assert resultado.motivo == "sin_pedido"
    assert llamadas == []


def test_pedido_no_aplicable_no_prepara():
    _, llamadas, resultado = ejecutar(
        aplica=False,
    )

    assert resultado.habilitada is False
    assert resultado.motivo == "no_aplica"
    assert llamadas == []


def test_sin_contacto_no_prepara():
    pedido = SimpleNamespace(
        contacto_iniciado=False,
    )

    _, llamadas, resultado = ejecutar(
        pedido=pedido,
    )

    assert resultado.habilitada is False
    assert resultado.motivo == "sin_contacto"
    assert llamadas == []


def test_preparacion_conserva_seller_id():
    _, llamadas, resultado = ejecutar(
        seller_id="cuenta-nautica",
    )

    preparar = next(
        llamada
        for llamada in llamadas
        if llamada[0] == "preparar"
    )

    assert (
        preparar[2]["seller_id"]
        == "cuenta-nautica"
    )
    assert resultado.habilitada is True
    assert resultado.texto_ultimo == "último"
    assert resultado.texto == "mensaje"


def test_sin_mensaje_no_habilita():
    _, llamadas, resultado = ejecutar(
        mensaje=False,
    )

    assert resultado.habilitada is False
    assert resultado.motivo == "sin_mensaje"
    assert not any(
        llamada[0] == "marcar"
        for llamada in llamadas
    )


def test_texto_marca_respuesta_sin_commit():
    pedido, llamadas, resultado = ejecutar()

    marcar = next(
        llamada
        for llamada in llamadas
        if llamada[0] == "marcar"
    )

    assert marcar[1][0] is pedido
    assert marcar[2] == {
        "canal": "mercadolibre",
        "commit": False,
    }
    assert resultado.habilitada is True


def test_texto_vacio_no_marca_respuesta():
    _, llamadas, resultado = ejecutar(
        texto="",
    )

    assert resultado.habilitada is True
    assert resultado.texto == ""
    assert not any(
        llamada[0] == "marcar"
        for llamada in llamadas
    )
