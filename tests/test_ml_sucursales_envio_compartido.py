from datetime import datetime
from types import SimpleNamespace

from services.ml_sucursales_via_cargo import (
    enviar_sugerencia_sucursales_ml,
)


class SessionFake:
    def __init__(self, fallar_commit=False):
        self.commits = 0
        self.rollbacks = 0
        self.fallar_commit = fallar_commit

    def commit(self):
        self.commits += 1
        if self.fallar_commit:
            raise RuntimeError("fallo controlado")

    def rollback(self):
        self.rollbacks += 1


def pedido_base():
    return SimpleNamespace(
        id=31,
        ia_respuesta_sugerida="",
        ia_respuesta_enviada_hash="",
        ia_ultima_respuesta_enviada=None,
        ml_mensajes_pendientes=True,
        ml_mensajes_pendientes_count=2,
    )


def ejecutar(
    *,
    mensaje="Elegí una sucursal",
    permitido=True,
    motivo="bloqueado",
    fallar_commit=False,
):
    pedido = pedido_base()
    session = SessionFake(
        fallar_commit=fallar_commit
    )
    llamados = []
    fecha = datetime(2026, 7, 27, 9, 0, 0)

    resultado = enviar_sugerencia_sucursales_ml(
        pedido=pedido,
        sugerir_sucursales_fn=(
            lambda _pedido: mensaje
        ),
        puede_enviar_mensaje_fn=(
            lambda **_kwargs: (
                permitido,
                motivo,
            )
        ),
        enviar_mensaje_ml_fn=(
            lambda _pedido, texto: llamados.append(
                ("enviar", texto)
            )
        ),
        registrar_envio_automatico_fn=(
            lambda **kwargs: llamados.append(
                ("registrar", kwargs)
            )
        ),
        ia_hash_texto_fn=(
            lambda texto: f"hash:{texto}"
        ),
        db_session=session,
        motivo_ok="sucursales_enviadas",
        motivo_error="error_sucursales",
        now_fn=lambda: fecha,
        log_fn=lambda _texto: None,
    )

    return resultado, pedido, session, llamados, fecha


def test_sin_mensaje_no_interviene():
    resultado, _, session, llamados, _ = ejecutar(
        mensaje=None
    )

    assert resultado is None
    assert session.commits == 0
    assert llamados == []


def test_envia_con_motivo_configurado():
    resultado, pedido, session, llamados, fecha = (
        ejecutar()
    )

    assert resultado == {
        "ok": True,
        "motivo": "sucursales_enviadas",
    }
    assert llamados[0] == (
        "enviar",
        "Elegí una sucursal",
    )
    assert llamados[1][0] == "registrar"
    assert (
        pedido.ia_respuesta_sugerida
        == "Elegí una sucursal"
    )
    assert (
        pedido.ia_respuesta_enviada_hash
        == "hash:Elegí una sucursal"
    )
    assert pedido.ia_ultima_respuesta_enviada == fecha
    assert pedido.ml_mensajes_pendientes is False
    assert pedido.ml_mensajes_pendientes_count == 0
    assert session.commits == 1
    assert session.rollbacks == 0


def test_respeta_bloqueo_canal_manager():
    resultado, _, session, llamados, _ = ejecutar(
        permitido=False,
        motivo="wa_activo",
    )

    assert resultado == {
        "ok": False,
        "motivo": "wa_activo",
    }
    assert session.commits == 0
    assert llamados == []


def test_error_usa_motivo_configurado_y_rollback():
    resultado, _, session, _, _ = ejecutar(
        fallar_commit=True,
    )

    assert resultado == {
        "ok": False,
        "motivo": "error_sucursales",
    }
    assert session.commits == 1
    assert session.rollbacks == 1
