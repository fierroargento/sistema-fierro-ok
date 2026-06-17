from datetime import datetime

from services.ml_sucursales_via_cargo import intentar_ofrecer_sucursales_ml_antes_wa


class PedidoFake:
    def __init__(self):
        self.ia_respuesta_sugerida = ""
        self.ia_respuesta_enviada_hash = ""
        self.ia_ultima_respuesta_enviada = None
        self.ml_mensajes_pendientes = True
        self.ml_mensajes_pendientes_count = 3


class DbSessionFake:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_no_interviene_si_ml_esta_cortado():
    pedido = PedidoFake()
    llamados = []

    resultado = intentar_ofrecer_sucursales_ml_antes_wa(
        pedido=pedido,
        ml_cortado=True,
        sugerir_sucursales_fn=lambda pedido: llamados.append("sugerir"),
        puede_enviar_mensaje_fn=lambda **kwargs: llamados.append("puede"),
        enviar_mensaje_ml_fn=lambda pedido, texto: llamados.append("enviar"),
        registrar_envio_automatico_fn=lambda **kwargs: llamados.append("registrar"),
        ia_hash_texto_fn=lambda texto: "hash",
        db_session=DbSessionFake(),
        now_fn=datetime.utcnow,
    )

    assert resultado is None
    assert llamados == []


def test_envia_sucursales_por_ml_y_frena_whatsapp():
    pedido = PedidoFake()
    db_session = DbSessionFake()
    llamados = []

    resultado = intentar_ofrecer_sucursales_ml_antes_wa(
        pedido=pedido,
        ml_cortado=False,
        sugerir_sucursales_fn=lambda pedido: "Elegí una sucursal",
        puede_enviar_mensaje_fn=lambda **kwargs: (True, ""),
        enviar_mensaje_ml_fn=lambda pedido, texto: llamados.append(("enviar", texto)),
        registrar_envio_automatico_fn=lambda **kwargs: llamados.append(("registrar", kwargs["canal"], kwargs["texto"])),
        ia_hash_texto_fn=lambda texto: f"hash:{texto}",
        db_session=db_session,
        now_fn=lambda: datetime(2026, 6, 17, 10, 30),
    )

    assert resultado == {
        "ok": True,
        "motivo": "sucursales_ml_enviadas_antes_wa",
    }
    assert llamados == [
        ("enviar", "Elegí una sucursal"),
        ("registrar", "ml", "Elegí una sucursal"),
    ]
    assert pedido.ia_respuesta_sugerida == "Elegí una sucursal"
    assert pedido.ia_respuesta_enviada_hash == "hash:Elegí una sucursal"
    assert pedido.ia_ultima_respuesta_enviada == datetime(2026, 6, 17, 10, 30)
    assert pedido.ml_mensajes_pendientes is False
    assert pedido.ml_mensajes_pendientes_count == 0
    assert db_session.commits == 1
    assert db_session.rollbacks == 0


def test_frena_whatsapp_si_ml_activo_y_no_hay_sucursales_para_ofrecer():
    resultado = intentar_ofrecer_sucursales_ml_antes_wa(
        pedido=PedidoFake(),
        ml_cortado=False,
        sugerir_sucursales_fn=lambda pedido: None,
        puede_enviar_mensaje_fn=lambda **kwargs: (True, ""),
        enviar_mensaje_ml_fn=lambda pedido, texto: None,
        registrar_envio_automatico_fn=lambda **kwargs: None,
        ia_hash_texto_fn=lambda texto: "hash",
        db_session=DbSessionFake(),
        now_fn=datetime.utcnow,
    )

    assert resultado == {
        "ok": False,
        "motivo": "ml_debe_cerrar_sucursal",
    }


def test_respeta_bloqueo_del_canal_manager():
    llamados = []

    resultado = intentar_ofrecer_sucursales_ml_antes_wa(
        pedido=PedidoFake(),
        ml_cortado=False,
        sugerir_sucursales_fn=lambda pedido: "Elegí una sucursal",
        puede_enviar_mensaje_fn=lambda **kwargs: (False, "ml_bloqueado"),
        enviar_mensaje_ml_fn=lambda pedido, texto: llamados.append("enviar"),
        registrar_envio_automatico_fn=lambda **kwargs: llamados.append("registrar"),
        ia_hash_texto_fn=lambda texto: "hash",
        db_session=DbSessionFake(),
        now_fn=datetime.utcnow,
    )

    assert resultado == {
        "ok": False,
        "motivo": "ml_bloqueado",
    }
    assert llamados == []
