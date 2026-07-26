from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from services.ml_consultas_logisticas import (
    procesar_consulta_demora_simple_ml,
    texto_demora_handoff_wa_ml,
)


class SessionFake:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def pedido_base(**cambios):
    datos = {
        "id": 71,
        "ia_resumen": "Pregunta por demora",
        "ia_requiere_operador": True,
        "ia_recolector_estado": "requiere_operador",
        "sucursal_nombre": "",
        "wa_estado": "",
        "ia_sucursales_ofrecidas": None,
        "correo_sucursales_ofrecidas": None,
        "ia_respuesta_sugerida": "",
        "ia_respuesta_enviada_hash": "",
        "ia_ultima_respuesta_enviada": None,
        "ml_mensajes_pendientes": True,
        "ml_mensajes_pendientes_count": 2,
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def ejecutar(
    pedido,
    *,
    faltantes=None,
    plegable=False,
    bloquea_sucursal=False,
    duplicada=False,
    permitido=True,
    motivo_bloqueo="bloqueado",
    handoff=(True, "iniciado"),
    registrar_error=False,
    session=None,
    enviados=None,
    handoffs=None,
):
    session = session or SessionFake()
    enviados = enviados if enviados is not None else []
    handoffs = handoffs if handoffs is not None else []
    fecha = datetime(2026, 7, 26, 20, 0, 0)

    def registrar(**kwargs):
        if registrar_error:
            raise RuntimeError("fallo controlado")
        enviados.append(("registro", kwargs))

    def iniciar_wa(*args, **kwargs):
        handoffs.append((args, kwargs))
        return handoff

    resultado = procesar_consulta_demora_simple_ml(
        pedido,
        faltantes or [],
        es_ml_acordas_fn=lambda _pedido: True,
        pedido_es_plegable_fn=(
            lambda _pedido: plegable
        ),
        bloquea_inicio_wa_fn=(
            lambda _pedido: bloquea_sucursal
        ),
        respuesta_ya_enviada_fn=(
            lambda _pedido, _texto: duplicada
        ),
        puede_enviar_fn=(
            lambda **_kwargs: (
                permitido,
                motivo_bloqueo,
            )
        ),
        enviar_mensaje_fn=(
            lambda _pedido, texto: enviados.append(
                ("envio", texto)
            )
        ),
        registrar_envio_fn=registrar,
        hash_texto_fn=lambda texto: f"hash:{texto}",
        ahora_fn=lambda: fecha,
        wa_auto_iniciar_fn=iniciar_wa,
        db_session=session,
        log_fn=lambda _texto: None,
    )

    return resultado, session, enviados, handoffs, fecha


def test_no_procesa_si_hay_faltantes():
    resultado, session, enviados, handoffs, _ = (
        ejecutar(
            pedido_base(),
            faltantes=["dni"],
        )
    )

    assert resultado.procesada is False
    assert session.commits == 0
    assert enviados == []
    assert handoffs == []


def test_prioriza_sucursal_para_plegable():
    resultado, session, enviados, _, _ = ejecutar(
        pedido_base(),
        plegable=True,
    )

    assert resultado.procesada is False
    assert session.commits == 0
    assert enviados == []


def test_respuesta_duplicada_finaliza_sin_enviar():
    resultado, session, enviados, _, _ = ejecutar(
        pedido_base(),
        duplicada=True,
    )

    assert resultado.procesada is True
    assert resultado.ok is False
    assert resultado.motivo == "duplicada"
    assert session.commits == 0
    assert enviados == []


def test_canal_manager_bloquea_sin_enviar():
    resultado, session, enviados, _, _ = ejecutar(
        pedido_base(),
        permitido=False,
        motivo_bloqueo="wa_activo",
    )

    assert resultado.procesada is True
    assert resultado.ok is False
    assert resultado.motivo == "wa_activo"
    assert session.commits == 0
    assert enviados == []


def test_responde_persiste_y_luego_inicia_wa():
    pedido = pedido_base()
    resultado, session, enviados, handoffs, fecha = (
        ejecutar(pedido)
    )

    texto = texto_demora_handoff_wa_ml()

    assert resultado.procesada is True
    assert resultado.ok is True
    assert (
        resultado.motivo
        == "demora_respondida_wa_iniciado"
    )
    assert enviados[0] == ("envio", texto)
    assert enviados[1][0] == "registro"
    assert pedido.ia_respuesta_sugerida == texto
    assert (
        pedido.ia_respuesta_enviada_hash
        == f"hash:{texto}"
    )
    assert pedido.ia_ultima_respuesta_enviada == fecha
    assert pedido.ml_mensajes_pendientes is False
    assert pedido.ml_mensajes_pendientes_count == 0
    assert pedido.ia_requiere_operador is False
    assert (
        pedido.ia_recolector_estado
        == "datos_completos"
    )
    assert session.commits == 1
    assert len(handoffs) == 1
    assert handoffs[0][1] == {
        "faltantes": [],
        "motivo": (
            "consulta_demora_datos_completos"
        ),
    }


def test_conserva_motivo_si_wa_no_inicia():
    resultado, session, _, handoffs, _ = ejecutar(
        pedido_base(),
        handoff=(False, "sin_telefono"),
    )

    assert resultado.procesada is True
    assert resultado.ok is True
    assert (
        resultado.motivo
        == "demora_respondida_sin_telefono"
    )
    assert session.commits == 1
    assert len(handoffs) == 1


def test_error_de_envio_hace_rollback_y_no_inicia_wa():
    resultado, session, _, handoffs, _ = ejecutar(
        pedido_base(),
        registrar_error=True,
    )

    assert resultado.procesada is True
    assert resultado.ok is False
    assert resultado.motivo == "error_demora_ml"
    assert session.commits == 0
    assert session.rollbacks == 1
    assert handoffs == []


def test_app_delega_flujo_completo_de_demora():
    app = Path("app.py").read_text(encoding="utf-8")

    inicio = app.index(
        "def ia_auto_responder_post_analisis("
    )
    fin = app.find("\ndef ", inicio + 1)
    bloque = app[inicio:fin]

    assert (
        "procesar_consulta_demora_simple_ml("
        in bloque
    )
    assert (
        "if resultado_demora.procesada:"
        in bloque
    )
    assert "debe_priorizar_sucursal_ml" not in bloque
    assert "texto_demora_handoff_wa_ml" not in bloque
    assert "error_demora_ml" not in bloque
    assert (
        "consulta_demora_datos_completos"
        not in bloque
    )
