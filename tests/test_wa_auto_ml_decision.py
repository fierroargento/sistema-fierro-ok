from services.wa_auto_ml_decision import (
    agregar_marca_a_resumen_si_falta,
    construir_detalle_auditoria_wa_desde_ml,
    construir_log_error_wa_auto_ml,
    construir_log_ml_debe_cerrar_sucursal,
    construir_log_ml_sigue_recolectando,
    construir_log_wa_auto_ml_ok,
    construir_marca_ml_sigue_recolectando,
    decidir_flujo_wa_desde_ml,
    decidir_resultado_error_wa_desde_ml,
    decidir_resultado_final_wa_desde_ml,
    decidir_resultado_ml_debe_cerrar_sucursal,
    decidir_resultado_ml_sigue_recolectando,
    limpiar_faltantes_para_handoff_wa,
    limpiar_pendientes_ml_post_handoff,
    marca_wa_iniciado_desde_ml,
)


class PedidoFake:
    def __init__(self, localidad="", provincia=""):
        self.localidad = localidad
        self.provincia = provincia


def test_limpiar_faltantes_elimina_vacios():
    pedido = PedidoFake()

    resultado = limpiar_faltantes_para_handoff_wa(
        pedido,
        faltantes=["", None, "dni"],
        telefono_normalizado="",
    )

    assert resultado == ["dni"]


def test_limpiar_faltantes_elimina_telefono_si_ya_hay_telefono_normalizado():
    pedido = PedidoFake()

    resultado = limpiar_faltantes_para_handoff_wa(
        pedido,
        faltantes=["telefono", "dni"],
        telefono_normalizado="5492920123456",
    )

    assert resultado == ["dni"]


def test_limpiar_faltantes_mantiene_telefono_si_no_hay_telefono_normalizado():
    pedido = PedidoFake()

    resultado = limpiar_faltantes_para_handoff_wa(
        pedido,
        faltantes=["telefono", "dni"],
        telefono_normalizado="",
    )

    assert resultado == ["telefono", "dni"]


def test_limpiar_faltantes_elimina_localidad_y_provincia_si_ya_existen():
    pedido = PedidoFake(localidad="Viedma", provincia="Rio Negro")

    resultado = limpiar_faltantes_para_handoff_wa(
        pedido,
        faltantes=["localidad", "provincia", "direccion"],
        telefono_normalizado="",
    )

    assert resultado == ["direccion"]


def test_limpiar_faltantes_deduplica_manteniendo_orden():
    pedido = PedidoFake()

    resultado = limpiar_faltantes_para_handoff_wa(
        pedido,
        faltantes=["dni", "telefono", "dni", "direccion", "telefono"],
        telefono_normalizado="",
    )

    assert resultado == ["dni", "telefono", "direccion"]


def test_limpiar_faltantes_devuelve_lista_vacia_sin_faltantes():
    pedido = PedidoFake()

    resultado = limpiar_faltantes_para_handoff_wa(
        pedido,
        faltantes=None,
        telefono_normalizado="",
    )

    assert resultado == []

def test_construir_marca_ml_sigue_recolectando_con_faltantes():
    marca = construir_marca_ml_sigue_recolectando(["dni", "direccion"])

    assert marca == (
        "ML sigue recolectando datos; WA no iniciado por faltantes: "
        "dni, direccion"
    )


def test_construir_marca_ml_sigue_recolectando_limpia_vacios():
    marca = construir_marca_ml_sigue_recolectando(["dni", "", None, "telefono"])

    assert marca == (
        "ML sigue recolectando datos; WA no iniciado por faltantes: "
        "dni, telefono"
    )


def test_construir_marca_ml_sigue_recolectando_sin_faltantes():
    marca = construir_marca_ml_sigue_recolectando([])

    assert marca == "ML sigue recolectando datos; WA no iniciado por faltantes"

def test_agregar_marca_a_resumen_si_falta_agrega_con_separador():
    resultado = agregar_marca_a_resumen_si_falta(
        "Resumen previo",
        "Marca nueva",
    )

    assert resultado == "Resumen previo | Marca nueva"


def test_agregar_marca_a_resumen_si_falta_no_duplica():
    resultado = agregar_marca_a_resumen_si_falta(
        "Resumen previo | Marca nueva",
        "Marca nueva",
    )

    assert resultado == "Resumen previo | Marca nueva"


def test_agregar_marca_a_resumen_si_falta_soporta_resumen_vacio():
    resultado = agregar_marca_a_resumen_si_falta(
        "",
        "Marca nueva",
    )

    assert resultado == "Marca nueva"


def test_agregar_marca_a_resumen_si_falta_ignora_marca_vacia():
    resultado = agregar_marca_a_resumen_si_falta(
        "Resumen previo",
        "",
    )

    assert resultado == "Resumen previo"


def test_agregar_marca_a_resumen_si_falta_respeta_limite():
    resultado = agregar_marca_a_resumen_si_falta(
        "A" * 20,
        "B" * 20,
        limite=10,
    )

    assert resultado == "A" * 10

def test_decidir_resultado_ml_sigue_recolectando_devuelve_corte_si_ml_no_cortado():
    resultado = decidir_resultado_ml_sigue_recolectando(False)

    assert resultado == {
        "ok": False,
        "motivo": "ml_sigue_recolectando",
    }


def test_decidir_resultado_ml_sigue_recolectando_devuelve_none_si_ml_cortado():
    resultado = decidir_resultado_ml_sigue_recolectando(True)

    assert resultado is None

def test_decidir_flujo_wa_desde_ml_con_faltantes():
    resultado = decidir_flujo_wa_desde_ml(["dni", "direccion"])

    assert resultado == {
        "flujo": "faltantes",
        "accion": "Inició WhatsApp desde ML",
        "detalle_extra": "handoff ML→WA con ML cortado | dni, direccion",
    }


def test_decidir_flujo_wa_desde_ml_limpia_faltantes_vacios():
    resultado = decidir_flujo_wa_desde_ml(["dni", "", None, "telefono"])

    assert resultado == {
        "flujo": "faltantes",
        "accion": "Inició WhatsApp desde ML",
        "detalle_extra": "handoff ML→WA con ML cortado | dni, telefono",
    }


def test_decidir_flujo_wa_desde_ml_sin_faltantes():
    resultado = decidir_flujo_wa_desde_ml([])

    assert resultado == {
        "flujo": "datos_completos",
        "accion": "Inició WhatsApp con datos completos",
        "detalle_extra": "datos completos | cross-sell evaluado post handoff ML",
    }


def test_decidir_flujo_wa_desde_ml_con_none():
    resultado = decidir_flujo_wa_desde_ml(None)

    assert resultado == {
        "flujo": "datos_completos",
        "accion": "Inició WhatsApp con datos completos",
        "detalle_extra": "datos completos | cross-sell evaluado post handoff ML",
    }

def test_marca_wa_iniciado_desde_ml():
    assert marca_wa_iniciado_desde_ml() == "WA iniciado automáticamente desde ML"


def test_agregar_marca_wa_iniciado_desde_ml_a_resumen():
    marca = marca_wa_iniciado_desde_ml()

    resultado = agregar_marca_a_resumen_si_falta(
        "Resumen previo",
        marca,
    )

    assert resultado == "Resumen previo | WA iniciado automáticamente desde ML"


def test_agregar_marca_wa_iniciado_desde_ml_no_duplica():
    marca = marca_wa_iniciado_desde_ml()

    resultado = agregar_marca_a_resumen_si_falta(
        "Resumen previo | WA iniciado automáticamente desde ML",
        marca,
    )

    assert resultado == "Resumen previo | WA iniciado automáticamente desde ML"

class PedidoPendientesMlFake:
    def __init__(self):
        self.ml_mensajes_pendientes = True
        self.ml_mensajes_pendientes_count = 3


def test_limpiar_pendientes_ml_post_handoff_limpia_flags():
    pedido = PedidoPendientesMlFake()

    resultado = limpiar_pendientes_ml_post_handoff(pedido)

    assert resultado is True
    assert pedido.ml_mensajes_pendientes is False
    assert pedido.ml_mensajes_pendientes_count == 0


def test_limpiar_pendientes_ml_post_handoff_devuelve_false_si_no_puede_mutar():
    class PedidoRoto:
        @property
        def ml_mensajes_pendientes(self):
            return True

        @ml_mensajes_pendientes.setter
        def ml_mensajes_pendientes(self, valor):
            raise RuntimeError("no se puede escribir")

    pedido = PedidoRoto()

    resultado = limpiar_pendientes_ml_post_handoff(pedido)

    assert resultado is False

def test_construir_detalle_auditoria_wa_desde_ml():
    detalle = construir_detalle_auditoria_wa_desde_ml(
        "5492920123456",
        "handoff ML→WA con ML cortado | dni",
        "datos_incompletos",
    )

    assert detalle == (
        "Origen ML/Acordás. Teléfono: 5492920123456. "
        "handoff ML→WA con ML cortado | dni. "
        "Motivo: datos_incompletos"
    )


def test_construir_detalle_auditoria_wa_desde_ml_normaliza_vacios():
    detalle = construir_detalle_auditoria_wa_desde_ml(
        None,
        "",
        None,
    )

    assert detalle == "Origen ML/Acordás. Teléfono: . . Motivo: "

def test_decidir_resultado_final_wa_desde_ml_ok():
    assert decidir_resultado_final_wa_desde_ml(True) == (True, "enviado")


def test_decidir_resultado_final_wa_desde_ml_no_ok():
    assert decidir_resultado_final_wa_desde_ml(False) == (False, "wa_no_enviado")

def test_decidir_resultado_ml_debe_cerrar_sucursal_devuelve_bloqueo():
    resultado = decidir_resultado_ml_debe_cerrar_sucursal(True)

    assert resultado == {
        "ok": False,
        "motivo": "ml_debe_cerrar_sucursal",
    }


def test_decidir_resultado_ml_debe_cerrar_sucursal_devuelve_none_si_no_bloquea():
    resultado = decidir_resultado_ml_debe_cerrar_sucursal(False)

    assert resultado is None

def test_decidir_resultado_error_wa_desde_ml_con_exception():
    error = RuntimeError("fallo general")

    assert decidir_resultado_error_wa_desde_ml(error) == (False, "fallo general")


def test_decidir_resultado_error_wa_desde_ml_con_texto():
    assert decidir_resultado_error_wa_desde_ml("error simple") == (False, "error simple")

def test_construir_log_ml_sigue_recolectando():
    assert construir_log_ml_sigue_recolectando(123, ["dni", "direccion"]) == (
        "[WA-AUTO-ML] NO inicia WA pedido #123: ML activo sigue recolectando (dni, direccion)"
    )


def test_construir_log_ml_sigue_recolectando_sin_faltantes():
    assert construir_log_ml_sigue_recolectando(123, []) == (
        "[WA-AUTO-ML] NO inicia WA pedido #123: ML activo sigue recolectando ()"
    )


def test_construir_log_ml_debe_cerrar_sucursal():
    assert construir_log_ml_debe_cerrar_sucursal(456) == (
        "[WA-AUTO-ML] No se inicia WhatsApp pedido #456: ML debe cerrar sucursal primero."
    )


def test_construir_log_wa_auto_ml_ok():
    assert construir_log_wa_auto_ml_ok(789, "Inició WhatsApp", "datos completos") == (
        "[WA-AUTO-ML] OK pedido #789: Inició WhatsApp (datos completos)"
    )


def test_construir_log_error_wa_auto_ml():
    assert construir_log_error_wa_auto_ml(321, "fallo") == (
        "[WA-AUTO-ML] Error pedido #321: fallo"
    )
