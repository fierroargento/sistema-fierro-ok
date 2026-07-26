from types import SimpleNamespace

from services.canal_manager import (
    evaluar_ownership_wa_para_respuesta_ml,
)


def pedido_base(**cambios):
    datos = {
        "wa_estado": "",
        "ia_canal_activo": "",
        "tipo_entrega": "",
        "empresa_envio": "",
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def evaluar(pedido, estado=None, *, obtener_error=False):
    def obtener_estado(
        _pedido,
        crear_si_no_existe=True,
    ):
        assert crear_si_no_existe is False
        if obtener_error:
            raise RuntimeError("fallo controlado")
        return estado

    return evaluar_ownership_wa_para_respuesta_ml(
        pedido,
        obtener_estado_conversacional_fn=obtener_estado,
    )


def test_wa_estado_real_bloquea_ml():
    resultado = evaluar(
        pedido_base(wa_estado="recolectando_datos")
    )

    assert resultado.bloquea is True
    assert (
        resultado.motivo
        == "wa_activo_recolectando_datos"
    )
    assert resultado.wa_estado == "recolectando_datos"


def test_requiere_operador_no_transfiere_ownership():
    resultado = evaluar(
        pedido_base(wa_estado="requiere_operador")
    )

    assert resultado.bloquea is False
    assert resultado.motivo == ""


def test_canal_conversacional_wa_bloquea_con_estado_real():
    estado = SimpleNamespace(
        canal_activo="whatsapp",
        takeover_activo=False,
        bot_pausado=False,
    )

    resultado = evaluar(
        pedido_base(wa_estado="recolectando_datos"),
        estado,
    )

    assert resultado.bloquea is True


def test_takeover_activo_bloquea_aunque_no_haya_estado_wa():
    estado = SimpleNamespace(
        canal_activo="",
        takeover_activo=True,
        bot_pausado=False,
    )

    resultado = evaluar(
        pedido_base(),
        estado,
    )

    assert resultado.bloquea is True
    assert resultado.motivo == "wa_activo_"


def test_bot_pausado_bloquea_ml():
    estado = SimpleNamespace(
        canal_activo="",
        takeover_activo=False,
        bot_pausado=True,
    )

    resultado = evaluar(
        pedido_base(),
        estado,
    )

    assert resultado.bloquea is True


def test_canal_activo_wa_bloquea_con_estado_real():
    resultado = evaluar(
        pedido_base(
            wa_estado="recolectando_datos",
            ia_canal_activo="wa",
        )
    )

    assert resultado.bloquea is True


def test_error_consultando_estado_conserva_regla_del_pedido():
    resultado = evaluar(
        pedido_base(wa_estado="requiere_operador"),
        obtener_error=True,
    )

    assert resultado.bloquea is False


def test_sin_ownership_permite_respuesta_ml():
    estado = SimpleNamespace(
        canal_activo="ml",
        takeover_activo=False,
        bot_pausado=False,
    )

    resultado = evaluar(
        pedido_base(),
        estado,
    )

    assert resultado.bloquea is False
    assert resultado.motivo == ""
