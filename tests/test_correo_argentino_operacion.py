from services.correo_argentino_operacion import (
    aplicar_resumen_cotizacion_a_pedido,
    armar_lineas_cotizacion_cliente,
    extraer_resumen_cotizacion,
)


class PedidoFake:
    def __init__(self):
        self.empresa_envio = ""
        self.tipo_entrega = ""
        self.costo_envio = 0
        self.costo_envio_sucursal = 0
        self.costo_envio_domicilio = 0
        self.ia_resumen = ""


def test_extraer_resumen_cotizacion_sucursal():
    resultado = {
        "decision": "sucursal",
        "motivo": "Sucursal/Punto Correo preferido",
        "cp_destino": "1000",
        "sucursal": {
            "disponible": True,
            "precio": 13255.0,
            "servicio": "Correo Argentino Clasico",
        },
        "domicilio": {
            "disponible": True,
            "precio": 15957.0,
            "servicio": "Correo Argentino Clasico",
        },
    }

    r = extraer_resumen_cotizacion(resultado)

    assert r["ok"] is True
    assert r["transporte"] == "Correo Argentino"
    assert r["tipo_entrega"] == "Sucursal"
    assert r["precio_elegido"] == 13255.0
    assert r["precio_sucursal"] == 13255.0
    assert r["precio_domicilio"] == 15957.0
    assert r["servicio"] == "Correo Argentino Clasico"


def test_extraer_resumen_cotizacion_domicilio():
    resultado = {
        "decision": "domicilio",
        "motivo": "Domicilio aceptado por regla automática",
        "sucursal": {"disponible": True, "precio": 13255.0},
        "domicilio": {
            "disponible": True,
            "precio": 15957.0,
            "servicio": "Correo Argentino Expreso",
        },
    }

    r = extraer_resumen_cotizacion(resultado)

    assert r["ok"] is True
    assert r["tipo_entrega"] == "Domicilio"
    assert r["precio_elegido"] == 15957.0
    assert r["servicio"] == "Correo Argentino Expreso"


def test_extraer_resumen_cotizacion_escalar_no_aplica():
    r = extraer_resumen_cotizacion({
        "decision": "escalar",
        "motivo": "No hay sucursal disponible; solo domicilio",
    })

    assert r["ok"] is False
    assert r["tipo_entrega"] == ""
    assert r["precio_elegido"] == 0


def test_aplicar_resumen_cotizacion_a_pedido_no_hace_commit():
    pedido = PedidoFake()
    resumen = extraer_resumen_cotizacion({
        "decision": "sucursal",
        "motivo": "Sucursal/Punto Correo preferido",
        "sucursal": {"disponible": True, "precio": 13255.0},
        "domicilio": {"disponible": True, "precio": 15957.0},
    })

    ok, mensaje = aplicar_resumen_cotizacion_a_pedido(pedido, resumen)

    assert ok is True
    assert mensaje == "Correo Argentino aplicado (Sucursal)"
    assert pedido.empresa_envio == "Correo Argentino"
    assert pedido.tipo_entrega == "Sucursal"
    assert pedido.costo_envio == 13255.0
    assert pedido.costo_envio_sucursal == 13255.0
    assert pedido.costo_envio_domicilio == 15957.0
    assert "Correo Argentino evaluado" in pedido.ia_resumen


def test_aplicar_resumen_no_ok_no_modifica_pedido():
    pedido = PedidoFake()

    ok, mensaje = aplicar_resumen_cotizacion_a_pedido(pedido, {
        "ok": False,
        "motivo": "Revisión manual",
    })

    assert ok is False
    assert mensaje == "Revisión manual"
    assert pedido.empresa_envio == ""
    assert pedido.tipo_entrega == ""


def test_armar_lineas_cotizacion_cliente():
    resumen = {
        "precio_sucursal": 13255.0,
        "precio_domicilio": 15957.0,
        "servicio": "Correo Argentino Clasico",
        "motivo": "Sucursal/Punto Correo preferido",
    }

    lineas = armar_lineas_cotizacion_cliente(resumen)

    assert "Sucursal: $13255" in lineas
    assert "Domicilio: $15957" in lineas
    assert "Servicio elegido: Correo Argentino Clasico" in lineas
    assert "Motivo: Sucursal/Punto Correo preferido" in lineas


def test_preferencias_operativas_correo_default_fierro(monkeypatch):
    from services.correo_argentino_operacion import obtener_preferencias_operativas_correo

    for key in [
        "CORREO_MODALIDAD_PREFERIDA",
        "CORREO_DOMICILIO_PERMITIDO",
        "CORREO_MICORREO_SERVICIO_PREFERIDO",
        "CORREO_CANTIDAD_SUCURSALES_CLIENTE",
        "CORREO_MOSTRAR_COSTOS_CLIENTE",
        "CORREO_REQUIERE_OPERADOR_PAGO_ETIQUETA",
    ]:
        monkeypatch.delenv(key, raising=False)

    r = obtener_preferencias_operativas_correo()

    assert r["modalidad_preferida"] == "sucursal"
    assert r["domicilio_permitido"] is True
    assert r["servicio_preferido"] == "clasico"
    assert r["cantidad_sucursales_cliente"] == 3
    assert r["mostrar_costos_cliente"] is False
    assert r["requiere_operador_para_pago_etiqueta"] is True


def test_preferencias_operativas_correo_saas_configurable(monkeypatch):
    from services.correo_argentino_operacion import obtener_preferencias_operativas_correo

    monkeypatch.setenv("CORREO_MODALIDAD_PREFERIDA", "domicilio")
    monkeypatch.setenv("CORREO_DOMICILIO_PERMITIDO", "false")
    monkeypatch.setenv("CORREO_MICORREO_SERVICIO_PREFERIDO", "expreso")
    monkeypatch.setenv("CORREO_CANTIDAD_SUCURSALES_CLIENTE", "5")
    monkeypatch.setenv("CORREO_MOSTRAR_COSTOS_CLIENTE", "true")
    monkeypatch.setenv("CORREO_REQUIERE_OPERADOR_PAGO_ETIQUETA", "false")

    r = obtener_preferencias_operativas_correo()

    assert r["modalidad_preferida"] == "domicilio"
    assert r["domicilio_permitido"] is False
    assert r["servicio_preferido"] == "expreso"
    assert r["cantidad_sucursales_cliente"] == 5
    assert r["mostrar_costos_cliente"] is True
    assert r["requiere_operador_para_pago_etiqueta"] is False


def test_preferencias_operativas_correo_limita_cantidad_sucursales(monkeypatch):
    from services.correo_argentino_operacion import obtener_preferencias_operativas_correo

    monkeypatch.setenv("CORREO_CANTIDAD_SUCURSALES_CLIENTE", "99")

    r = obtener_preferencias_operativas_correo()

    assert r["cantidad_sucursales_cliente"] == 5


def test_preferencias_correo_acordas_default_umbral_cero(monkeypatch):
    from services.correo_argentino_operacion import obtener_preferencias_operativas_correo

    monkeypatch.delenv("CORREO_MAX_COSTO_SUCURSAL_ACORDAS", raising=False)

    r = obtener_preferencias_operativas_correo()

    assert r["priorizar_correo_sucursal_acordas"] is True
    assert r["max_costo_correo_sucursal_acordas"] == 0


def test_evaluar_prioridad_correo_acordas_no_aplica_sin_umbral():
    from services.correo_argentino_operacion import evaluar_prioridad_correo_sucursal_acordas

    r = evaluar_prioridad_correo_sucursal_acordas(
        {"disponible": True, "precio": 12000},
        es_acordas=True,
        es_pp6040=False,
        preferencias={
            "priorizar_correo_sucursal_acordas": True,
            "max_costo_correo_sucursal_acordas": 0,
        },
    )

    assert r["usar_correo"] is False
    assert "sin umbral" in r["motivo"].lower()


def test_evaluar_prioridad_correo_acordas_prioriza_si_precio_menor_al_umbral():
    from services.correo_argentino_operacion import evaluar_prioridad_correo_sucursal_acordas

    r = evaluar_prioridad_correo_sucursal_acordas(
        {"disponible": True, "precio": 12000},
        es_acordas=True,
        es_pp6040=False,
        preferencias={
            "priorizar_correo_sucursal_acordas": True,
            "max_costo_correo_sucursal_acordas": 15000,
        },
    )

    assert r["usar_correo"] is True
    assert r["precio"] == 12000
    assert r["umbral"] == 15000


def test_evaluar_prioridad_correo_acordas_no_prioriza_si_supera_umbral():
    from services.correo_argentino_operacion import evaluar_prioridad_correo_sucursal_acordas

    r = evaluar_prioridad_correo_sucursal_acordas(
        {"disponible": True, "precio": 18000},
        es_acordas=True,
        es_pp6040=False,
        preferencias={
            "priorizar_correo_sucursal_acordas": True,
            "max_costo_correo_sucursal_acordas": 15000,
        },
    )

    assert r["usar_correo"] is False
    assert "supera umbral" in r["motivo"].lower()


def test_evaluar_prioridad_correo_acordas_no_aplica_a_pp6040():
    from services.correo_argentino_operacion import evaluar_prioridad_correo_sucursal_acordas

    r = evaluar_prioridad_correo_sucursal_acordas(
        {"disponible": True, "precio": 10000},
        es_acordas=True,
        es_pp6040=True,
        preferencias={
            "priorizar_correo_sucursal_acordas": True,
            "max_costo_correo_sucursal_acordas": 15000,
        },
    )

    assert r["usar_correo"] is False
    assert "pp6040" in r["motivo"].lower()


class PedidoCorreoPendienteFake:
    def __init__(self):
        self.empresa_envio = "Correo Argentino"
        self.tipo_entrega = "Sucursal"
        self.ia_requiere_operador = False
        self.ml_mensajes_pendientes = False
        self.ml_mensajes_pendientes_count = 0
        self.ia_resumen = ""


def test_marcar_correo_sucursal_pendiente_operador_activa_revision_manual():
    from services.correo_argentino_operacion import marcar_correo_sucursal_pendiente_operador

    pedido = PedidoCorreoPendienteFake()

    r = marcar_correo_sucursal_pendiente_operador(pedido)

    assert r is True
    assert pedido.ia_requiere_operador is True
    assert pedido.ml_mensajes_pendientes is True
    assert pedido.ml_mensajes_pendientes_count == 1
    assert "pago/etiqueta manual" in pedido.ia_resumen


def test_marcar_correo_sucursal_pendiente_operador_no_aplica_a_via_cargo():
    from services.correo_argentino_operacion import marcar_correo_sucursal_pendiente_operador

    pedido = PedidoCorreoPendienteFake()
    pedido.empresa_envio = "Vía Cargo"

    r = marcar_correo_sucursal_pendiente_operador(pedido)

    assert r is False
    assert pedido.ia_requiere_operador is False
    assert pedido.ml_mensajes_pendientes is False
