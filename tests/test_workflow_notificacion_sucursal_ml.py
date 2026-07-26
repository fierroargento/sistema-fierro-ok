from pathlib import Path
from types import SimpleNamespace

import services.workflow_notificacion_sucursal_ml as workflow
from services.workflow_transicion_sucursal_ml import (
    ResultadoTransicionSucursalML,
)


def pedido_fake():
    return SimpleNamespace(
        id=31,
        cliente="Martín Fierro",
        ia_resumen="",
        ml_mensajes_pendientes=False,
        ml_mensajes_pendientes_count=0,
        ia_requiere_operador=False,
    )


def sucursal_fake():
    return {
        "nombre": "Correo Centro",
        "direccion": "San Martín 123",
    }


def ejecutar(**cambios):
    datos = {
        "pedido": pedido_fake(),
        "sucursal": sucursal_fake(),
        "texto_cliente": "Elijo esa sucursal",
        "puede_enviar_fn": lambda **_kwargs: (
            True,
            "ok",
        ),
        "enviar_mensaje_fn": (
            lambda *_args, **_kwargs: None
        ),
        "registrar_envio_fn": (
            lambda **_kwargs: None
        ),
        "wa_auto_iniciar_fn": (
            lambda *_args, **_kwargs: (
                True,
                "iniciado",
            )
        ),
        "db_session": SimpleNamespace(
            commit=lambda: None,
        ),
        "log_fn": lambda _mensaje: None,
    }
    datos.update(cambios)
    return workflow.notificar_sucursal_detectada_ml(
        **datos
    )


def test_notificacion_construye_mensaje_y_compone_servicios(
    monkeypatch,
):
    llamadas = []

    def transicion(**kwargs):
        llamadas.append(("transicion", kwargs))
        return ResultadoTransicionSucursalML(
            estado="enviada",
            motivo="enviada",
        )

    monkeypatch.setattr(
        workflow,
        "ejecutar_transicion_ml_tras_confirmacion_sucursal",
        transicion,
    )
    monkeypatch.setattr(
        workflow,
        "marcar_consulta_horarios_retiro_pendiente",
        lambda pedido, texto: (
            llamadas.append(
                ("consulta", pedido, texto)
            )
            or False
        ),
    )
    monkeypatch.setattr(
        workflow,
        "intentar_wa_cross_sell_tras_sucursal_ml",
        lambda pedido, **kwargs: (
            llamadas.append(
                ("cross_sell", pedido, kwargs)
            )
            or {"ok": True}
        ),
    )

    resultado = ejecutar()

    assert resultado.notificada is True
    assert "Muchas gracias Martín" in resultado.mensaje
    assert "Correo Centro" in resultado.mensaje
    assert "San Martín 123" in resultado.mensaje
    assert [item[0] for item in llamadas] == [
        "transicion",
        "consulta",
        "cross_sell",
    ]
    assert (
        llamadas[0][1][
            "continuar_si_motivo_repetido"
        ]
        is True
    )


def test_consulta_horarios_agrega_respuesta_y_marca():
    resultado = ejecutar(
        texto_cliente=(
            "¿Qué horarios tiene la sucursal "
            "para retirar?"
        ),
    )

    assert resultado.notificada is True
    assert "Sobre los horarios" in resultado.mensaje
    assert resultado.consulta_marcada is True


def test_transicion_omitida_devuelve_respuesta_compatible(
    monkeypatch,
):
    monkeypatch.setattr(
        workflow,
        "ejecutar_transicion_ml_tras_confirmacion_sucursal",
        lambda **_kwargs: (
            ResultadoTransicionSucursalML(
                estado="omitida",
                motivo="whatsapp_activo",
            )
        ),
    )

    resultado = ejecutar()

    assert resultado.estado == "omitida"
    assert resultado.respuesta_flujo == (
        False,
        "whatsapp_activo",
    )


def test_error_transicion_no_marca_ni_hace_cross_sell(
    monkeypatch,
):
    llamadas = []

    monkeypatch.setattr(
        workflow,
        "ejecutar_transicion_ml_tras_confirmacion_sucursal",
        lambda **_kwargs: (
            ResultadoTransicionSucursalML(
                estado="error",
                motivo="fallo ml",
            )
        ),
    )
    monkeypatch.setattr(
        workflow,
        "marcar_consulta_horarios_retiro_pendiente",
        lambda *_args: llamadas.append("consulta"),
    )
    monkeypatch.setattr(
        workflow,
        "intentar_wa_cross_sell_tras_sucursal_ml",
        lambda *_args, **_kwargs: (
            llamadas.append("cross_sell")
        ),
    )

    resultado = ejecutar()

    assert resultado.estado == "error"
    assert resultado.motivo == "fallo ml"
    assert llamadas == []


def test_errores_posteriores_no_anulan_notificacion(
    monkeypatch,
):
    def fallar_consulta(*_args):
        raise RuntimeError("fallo consulta")

    def fallar_cross_sell(*_args, **_kwargs):
        raise RuntimeError("fallo cross sell")

    monkeypatch.setattr(
        workflow,
        "marcar_consulta_horarios_retiro_pendiente",
        fallar_consulta,
    )
    monkeypatch.setattr(
        workflow,
        "intentar_wa_cross_sell_tras_sucursal_ml",
        fallar_cross_sell,
    )

    resultado = ejecutar()

    assert resultado.notificada is True
    assert resultado.error_consulta == "fallo consulta"
    assert (
        resultado.error_cross_sell
        == "fallo cross sell"
    )


def test_servicio_no_depende_de_app():
    texto = Path(
        "services/workflow_notificacion_sucursal_ml.py"
    ).read_text(encoding="utf-8-sig")

    assert "from app import" not in texto
    assert "import app" not in texto
    assert "from flask import" not in texto
