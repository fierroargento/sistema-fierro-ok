from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from services.ia_auto_respuesta_ml import (
    enviar_auto_respuesta_ml,
)


def pedido_base(**cambios):
    datos = {
        "id": 91,
        "ia_respuesta_sugerida": "",
        "ia_respuesta_enviada_hash": "",
        "ia_ultima_respuesta_enviada": None,
        "ia_requiere_operador": False,
        "ia_recolector_estado": "",
        "ml_mensajes_pendientes": False,
        "ml_mensajes_pendientes_count": 0,
        "ia_resumen": "",
        "ia_error": "",
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def ejecutar(
    pedido,
    texto="Necesitamos tu DNI",
    *,
    requiere_operador=False,
    faltantes=None,
    duplicada=False,
    permitido=True,
    motivo_bloqueo="bloqueado",
    error_envio=False,
):
    enviados = []
    registros = []
    logs = []
    fecha = datetime(2026, 7, 26, 21, 0, 0)

    def enviar(*args, **kwargs):
        if error_envio:
            raise RuntimeError("fallo controlado")
        enviados.append((args, kwargs))

    resultado = enviar_auto_respuesta_ml(
        pedido,
        texto,
        requiere_operador=requiere_operador,
        faltantes=faltantes or [],
        respuesta_ya_enviada_fn=(
            lambda _pedido, _texto: duplicada
        ),
        puede_enviar_fn=(
            lambda **_kwargs: (
                permitido,
                motivo_bloqueo,
            )
        ),
        enviar_mensaje_fn=enviar,
        registrar_envio_fn=(
            lambda **kwargs: registros.append(
                kwargs
            )
        ),
        hash_texto_fn=lambda valor: f"hash:{valor}",
        ahora_fn=lambda: fecha,
        log_fn=logs.append,
    )

    return (
        resultado,
        enviados,
        registros,
        logs,
        fecha,
    )


def test_sin_texto_no_envia():
    resultado, enviados, registros, _, _ = ejecutar(
        pedido_base(),
        texto="   ",
    )

    assert resultado.ok is False
    assert resultado.motivo == "sin_texto"
    assert enviados == []
    assert registros == []


def test_respuesta_duplicada_no_envia():
    resultado, enviados, registros, _, _ = ejecutar(
        pedido_base(),
        duplicada=True,
    )

    assert resultado.ok is False
    assert resultado.motivo == "duplicada"
    assert enviados == []
    assert registros == []


def test_canal_manager_bloquea_envio():
    resultado, enviados, registros, logs, _ = (
        ejecutar(
            pedido_base(),
            permitido=False,
            motivo_bloqueo="wa_activo",
        )
    )

    assert resultado.ok is False
    assert resultado.motivo == "wa_activo"
    assert enviados == []
    assert registros == []
    assert "wa_activo" in logs[0]


def test_envio_normal_limpia_pendientes():
    pedido = pedido_base(
        ml_mensajes_pendientes=True,
        ml_mensajes_pendientes_count=3,
    )

    resultado, enviados, registros, _, fecha = (
        ejecutar(pedido)
    )

    assert resultado.ok is True
    assert resultado.motivo == "enviada"
    assert len(enviados) == 1
    assert enviados[0][1] == {
        "permitir_requiere_operador": False,
    }
    assert registros == [
        {
            "pedido": pedido,
            "canal": "ml",
            "texto": "Necesitamos tu DNI",
        }
    ]
    assert (
        pedido.ia_respuesta_sugerida
        == "Necesitamos tu DNI"
    )
    assert (
        pedido.ia_respuesta_enviada_hash
        == "hash:Necesitamos tu DNI"
    )
    assert pedido.ia_ultima_respuesta_enviada == fecha
    assert pedido.ml_mensajes_pendientes is False
    assert pedido.ml_mensajes_pendientes_count == 0
    assert (
        "IA respondió automáticamente"
        in pedido.ia_resumen
    )


def test_operador_con_faltantes_habilita_envio():
    pedido = pedido_base()

    resultado, enviados, _, _, _ = ejecutar(
        pedido,
        requiere_operador=True,
        faltantes=["dni"],
    )

    assert resultado.ok is True
    assert enviados[0][1] == {
        "permitir_requiere_operador": True,
    }
    assert pedido.ia_requiere_operador is True
    assert (
        pedido.ia_recolector_estado
        == "requiere_operador"
    )
    assert pedido.ml_mensajes_pendientes is True
    assert pedido.ml_mensajes_pendientes_count == 1
    assert (
        "consulta pendiente para operador"
        in pedido.ia_resumen
    )


def test_operador_sin_faltantes_no_abre_excepcion_envio():
    pedido = pedido_base()

    resultado, enviados, _, _, _ = ejecutar(
        pedido,
        requiere_operador=True,
        faltantes=[],
    )

    assert resultado.ok is True
    assert enviados[0][1] == {
        "permitir_requiere_operador": False,
    }
    assert pedido.ia_requiere_operador is True
    assert pedido.ml_mensajes_pendientes is True


def test_error_de_envio_marca_error_controlado():
    pedido = pedido_base()

    resultado, _, registros, logs, _ = ejecutar(
        pedido,
        error_envio=True,
    )

    assert resultado.ok is False
    assert resultado.motivo == "error_envio"
    assert registros == []
    assert "fallo controlado" in pedido.ia_error
    assert len(logs) == 1


def test_app_delega_envio_final_al_servicio():
    app = Path("app.py").read_text(encoding="utf-8")

    inicio = app.index(
        "def ia_auto_responder_post_analisis("
    )
    fin = app.find("\ndef ", inicio + 1)
    bloque = app[inicio:fin]

    assert "enviar_auto_respuesta_ml(" in bloque
    assert (
        "requiere_operador=("
        in bloque
    )
    assert "faltantes=faltantes" in bloque
    assert (
        "resultado_envio.motivo"
        in bloque
    )

    prohibidos = [
        "permitir_requiere_operador=bool(",
        "IA respondió automáticamente",
        "IA respondió y dejó consulta",
        "construir_log_error_wa_auto_ml",
        'return False, "error_envio"',
    ]

    for prohibido in prohibidos:
        assert prohibido not in bloque
