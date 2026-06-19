from services.ml_sucursal_cross_sell_guard import (
    MARCA_AUTOAVANCE_REVERTIDO,
    intentar_wa_cross_sell_tras_sucursal_ml,
    debe_bloquear_autoavance_etiqueta_lista_por_cross_sell,
    aplicar_reversion_autoavance_si_corresponde,
)


class PedidoFake:
    def __init__(self):
        self.estado = "Cargando Pedido"
        self.ia_resumen = ""
        self.ml_mensajes_pendientes = False
        self.ia_requiere_operador = False


class DbFake:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


def test_intentar_wa_cross_sell_ok_no_marca_pendiente():
    pedido = PedidoFake()

    def wa_ok(pedido, faltantes, motivo):
        return True, "wa_iniciado"

    resultado = intentar_wa_cross_sell_tras_sucursal_ml(pedido, wa_ok)

    assert resultado["ok"] is True
    assert pedido.ml_mensajes_pendientes is False
    assert pedido.ia_requiere_operador is False
    assert pedido.ia_resumen == ""


def test_intentar_wa_cross_sell_falla_marca_pendiente_y_commitea():
    pedido = PedidoFake()
    db = DbFake()

    def wa_falla(pedido, faltantes, motivo):
        return False, "telefono_faltante"

    resultado = intentar_wa_cross_sell_tras_sucursal_ml(pedido, wa_falla, db_session=db)

    assert resultado["ok"] is False
    assert pedido.ml_mensajes_pendientes is True
    assert pedido.ia_requiere_operador is True
    assert "telefono_faltante" in pedido.ia_resumen
    assert db.commits == 1


def test_intentar_wa_cross_sell_error_marca_error():
    pedido = PedidoFake()

    def wa_error(pedido, faltantes, motivo):
        raise RuntimeError("fallo wa")

    resultado = intentar_wa_cross_sell_tras_sucursal_ml(pedido, wa_error)

    assert resultado["ok"] is False
    assert pedido.ml_mensajes_pendientes is True
    assert pedido.ia_requiere_operador is True
    assert "CROSS-SELL/WA error tras confirmar sucursal ML" in pedido.ia_resumen
    assert "fallo wa" in pedido.ia_resumen


def test_debe_bloquear_autoavance_solo_evalua_si_estado_cargando():
    pedido = PedidoFake()

    def regla(pedido, auto_enabled, manual_enabled, evento_operativo_model):
        return auto_enabled and manual_enabled

    assert debe_bloquear_autoavance_etiqueta_lista_por_cross_sell(
        pedido,
        estado_cargando="Cargando Pedido",
        cross_sell_rule_fn=regla,
        auto_enabled=True,
        manual_enabled=True,
        evento_operativo_model=object,
    ) is True

    pedido.estado = "Etiqueta Lista"

    assert debe_bloquear_autoavance_etiqueta_lista_por_cross_sell(
        pedido,
        estado_cargando="Cargando Pedido",
        cross_sell_rule_fn=regla,
        auto_enabled=True,
        manual_enabled=True,
        evento_operativo_model=object,
    ) is False


def test_aplicar_reversion_autoavance_si_corresponde():
    pedido = PedidoFake()
    pedido.estado = "Etiqueta Lista"

    nuevo_estado = aplicar_reversion_autoavance_si_corresponde(
        pedido,
        estado_anterior="Cargando Pedido",
        estado_etiqueta_lista="Etiqueta Lista",
        bloquear_cross_sell=True,
    )

    assert nuevo_estado == "Cargando Pedido"
    assert pedido.estado == "Cargando Pedido"
    assert pedido.ml_mensajes_pendientes is True
    assert pedido.ia_requiere_operador is True
    assert MARCA_AUTOAVANCE_REVERTIDO in pedido.ia_resumen
