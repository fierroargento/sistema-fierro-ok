from services.wa_auto_ml_recoleccion import manejar_ml_sigue_recolectando_si_corresponde


class PedidoDummy:
    def __init__(self, pedido_id=123, resumen=""):
        self.id = pedido_id
        self.ia_resumen = resumen


class DbSessionDummy:
    def __init__(self, falla_commit=False, falla_rollback=False):
        self.commits = 0
        self.rollbacks = 0
        self.falla_commit = falla_commit
        self.falla_rollback = falla_rollback

    def commit(self):
        self.commits += 1
        if self.falla_commit:
            raise RuntimeError("fallo commit")

    def rollback(self):
        self.rollbacks += 1
        if self.falla_rollback:
            raise RuntimeError("fallo rollback")


def test_manejar_ml_sigue_recolectando_no_hace_nada_si_no_hay_decision():
    pedido = PedidoDummy()
    db_session = DbSessionDummy()
    llamados = []

    resultado = manejar_ml_sigue_recolectando_si_corresponde(
        pedido=pedido,
        faltantes_limpios=["dni"],
        decision_ml_sigue=None,
        db_session=db_session,
        construir_marca_fn=lambda faltantes: llamados.append("marca"),
        agregar_marca_resumen_fn=lambda resumen, marca, limite: "resumen marcado",
        construir_log_fn=lambda pedido_id, faltantes: "log",
        print_fn=lambda texto: llamados.append(texto),
    )

    assert resultado is None
    assert pedido.ia_resumen == ""
    assert db_session.commits == 0
    assert db_session.rollbacks == 0
    assert llamados == []


def test_manejar_ml_sigue_recolectando_actualiza_resumen_commitea_loguea_y_devuelve_resultado():
    pedido = PedidoDummy(456, "resumen previo")
    db_session = DbSessionDummy()
    llamados = []

    resultado = manejar_ml_sigue_recolectando_si_corresponde(
        pedido=pedido,
        faltantes_limpios=["dni", "direccion"],
        decision_ml_sigue={"ok": False, "motivo": "ml_sigue_recolectando"},
        db_session=db_session,
        construir_marca_fn=lambda faltantes: "marca faltantes",
        agregar_marca_resumen_fn=lambda resumen, marca, limite: f"{resumen} | {marca} | {limite}",
        construir_log_fn=lambda pedido_id, faltantes: f"log {pedido_id} {','.join(faltantes)}",
        print_fn=lambda texto: llamados.append(texto),
    )

    assert resultado == (False, "ml_sigue_recolectando")
    assert pedido.ia_resumen == "resumen previo | marca faltantes | 1000"
    assert db_session.commits == 1
    assert db_session.rollbacks == 0
    assert llamados == ["log 456 dni,direccion"]


def test_manejar_ml_sigue_recolectando_si_falla_commit_hace_rollback_loguea_y_devuelve_resultado():
    pedido = PedidoDummy(789, "resumen previo")
    db_session = DbSessionDummy(falla_commit=True)
    llamados = []

    resultado = manejar_ml_sigue_recolectando_si_corresponde(
        pedido=pedido,
        faltantes_limpios=["dni"],
        decision_ml_sigue={"ok": False, "motivo": "ml_sigue_recolectando"},
        db_session=db_session,
        construir_marca_fn=lambda faltantes: "marca faltantes",
        agregar_marca_resumen_fn=lambda resumen, marca, limite: "resumen marcado",
        construir_log_fn=lambda pedido_id, faltantes: f"log {pedido_id}",
        print_fn=lambda texto: llamados.append(texto),
    )

    assert resultado == (False, "ml_sigue_recolectando")
    assert pedido.ia_resumen == "resumen marcado"
    assert db_session.commits == 1
    assert db_session.rollbacks == 1
    assert llamados == ["log 789"]
