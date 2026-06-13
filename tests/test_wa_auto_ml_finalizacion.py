from datetime import datetime

from services.wa_auto_ml_finalizacion import finalizar_wa_auto_ml_ok


class PedidoDummy:
    def __init__(self, pedido_id=123):
        self.id = pedido_id
        self.ia_resumen = ""
        self.wa_ultimo_contacto = None


class DbSessionDummy:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


def test_finalizar_wa_auto_ml_ok_actualiza_pedido_limpia_commitea_audita_loguea_y_devuelve_resultado():
    pedido = PedidoDummy(123)
    db_session = DbSessionDummy()
    ahora = datetime(2026, 1, 2, 3, 4, 5)
    llamados = []

    resultado = finalizar_wa_auto_ml_ok(
        pedido=pedido,
        resumen="resumen previo",
        marca="marca wa",
        tel="5492920123456",
        accion="Inició WhatsApp",
        detalle_extra="datos completos",
        motivo="handoff",
        now_fn=lambda: ahora,
        agregar_marca_a_resumen_fn=lambda resumen, marca, limite: f"{resumen} | {marca} | {limite}",
        limpiar_pendientes_fn=lambda p: llamados.append(("limpiar", p.id)),
        db_session=db_session,
        registrar_auditoria_fn=lambda **kwargs: llamados.append(("auditoria", kwargs)),
        construir_detalle_auditoria_fn=lambda tel, detalle, motivo: f"{tel} - {detalle} - {motivo}",
        construir_log_error_auditoria_fn=lambda pedido_id, error: f"error auditoria {pedido_id} {error}",
        construir_log_ok_fn=lambda pedido_id, accion, detalle: f"ok {pedido_id} {accion} {detalle}",
        decidir_resultado_final_fn=lambda ok: (ok, "enviado"),
        print_fn=lambda texto: llamados.append(("print", texto)),
    )

    assert resultado == (True, "enviado")
    assert pedido.wa_ultimo_contacto == ahora
    assert pedido.ia_resumen == "resumen previo | marca wa | 1000"
    assert db_session.commits == 1
    assert llamados[0] == ("limpiar", 123)
    assert llamados[1][0] == "auditoria"
    assert llamados[1][1] == {
        "accion": "Inició WhatsApp",
        "entidad": "pedido",
        "entidad_id": "123",
        "detalle": "5492920123456 - datos completos - handoff",
    }
    assert llamados[2] == ("print", "ok 123 Inició WhatsApp datos completos")


def test_finalizar_wa_auto_ml_ok_si_falla_auditoria_loguea_error_y_mantiene_resultado_ok():
    pedido = PedidoDummy(456)
    db_session = DbSessionDummy()
    llamados = []

    def auditoria_con_error(**kwargs):
        raise RuntimeError("fallo auditoria")

    resultado = finalizar_wa_auto_ml_ok(
        pedido=pedido,
        resumen="resumen",
        marca="marca",
        tel="5492920123456",
        accion="Inició WhatsApp",
        detalle_extra="datos completos",
        motivo="handoff",
        now_fn=lambda: datetime(2026, 1, 2, 3, 4, 5),
        agregar_marca_a_resumen_fn=lambda resumen, marca, limite: "resumen marcado",
        limpiar_pendientes_fn=lambda p: llamados.append(("limpiar", p.id)),
        db_session=db_session,
        registrar_auditoria_fn=auditoria_con_error,
        construir_detalle_auditoria_fn=lambda tel, detalle, motivo: "detalle",
        construir_log_error_auditoria_fn=lambda pedido_id, error: f"error auditoria {pedido_id} {error}",
        construir_log_ok_fn=lambda pedido_id, accion, detalle: f"ok {pedido_id}",
        decidir_resultado_final_fn=lambda ok: (ok, "enviado"),
        print_fn=lambda texto: llamados.append(("print", texto)),
    )

    assert resultado == (True, "enviado")
    assert pedido.ia_resumen == "resumen marcado"
    assert db_session.commits == 1
    assert llamados == [
        ("limpiar", 456),
        ("print", "error auditoria 456 fallo auditoria"),
        ("print", "ok 456"),
    ]
