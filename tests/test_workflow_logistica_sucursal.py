from types import SimpleNamespace

from services.workflow_logistica_sucursal import (
    aplicar_sucursal_elegida_al_pedido,
    normalizar_sucursal_operativa,
)


def test_normaliza_sucursal_via_cargo():
    sucursal = {
        "id": "vc-2",
        "nombre": "Terminal Formosa",
        "direccion": "Av. Gutnisky 2615",
        "localidad": "Formosa",
        "provincia": "Formosa",
    }

    datos = normalizar_sucursal_operativa(sucursal)

    assert datos["id"] == "vc-2"
    assert datos["nombre"] == "Terminal Formosa"
    assert datos["direccion"] == "Av. Gutnisky 2615"


def test_normaliza_sucursal_correo():
    sucursal = {
        "agencyId": "correo-1",
        "name": "Correo Centro",
        "address": "San Martin 123",
        "city": "Viedma",
        "province": "Rio Negro",
        "postalCode": "8500",
    }

    datos = normalizar_sucursal_operativa(sucursal)

    assert datos["id"] == "correo-1"
    assert datos["nombre"] == "Correo Centro"
    assert datos["direccion"] == "San Martin 123"
    assert datos["localidad"] == "Viedma"
    assert datos["provincia"] == "Rio Negro"
    assert datos["cp"] == "8500"


def test_aplica_sucursal_al_pedido_sin_commit_ni_mensajes():
    pedido = SimpleNamespace(
        sucursal_nombre="",
        direccion="",
        localidad="",
        provincia="",
        codigo_postal="3600",
        empresa_envio="",
        tipo_entrega="",
        ia_sucursales_ofrecidas='["vc-1", "vc-2"]',
        correo_sucursales_ofrecidas="[]",
        ia_requiere_operador=True,
        ia_esperando_respuesta=True,
        ml_mensajes_pendientes=True,
    )

    sucursal = {
        "id": "vc-2",
        "nombre": "Terminal Formosa Boleteria 5",
        "direccion": "Av. Gutnisky Nro.2615",
        "localidad": "Formosa",
        "provincia": "Formosa",
    }

    ok = aplicar_sucursal_elegida_al_pedido(
        pedido,
        sucursal,
        transporte="Vía Cargo",
    )

    assert ok is True
    assert pedido.sucursal_nombre == "Terminal Formosa Boleteria 5"
    assert pedido.direccion == "Av. Gutnisky Nro.2615"
    assert pedido.localidad == "Formosa"
    assert pedido.provincia == "Formosa"
    assert pedido.empresa_envio == "Vía Cargo"
    assert pedido.tipo_entrega == "Sucursal"
    assert pedido.ia_sucursales_ofrecidas is None
    assert pedido.correo_sucursales_ofrecidas is None
    assert pedido.ia_requiere_operador is False
    assert pedido.ia_esperando_respuesta is False
    assert pedido.ml_mensajes_pendientes is False


def test_no_pisa_transporte_existente():
    pedido = SimpleNamespace(
        sucursal_nombre="",
        direccion="",
        localidad="",
        provincia="",
        empresa_envio="Via Cargo",
        tipo_entrega="",
    )

    ok = aplicar_sucursal_elegida_al_pedido(
        pedido,
        {
            "nombre": "Agencia Formosa",
            "direccion": "Av. Italia 1856",
            "localidad": "Formosa",
            "provincia": "Formosa",
        },
        transporte="Correo Argentino",
    )

    assert ok is True
    assert pedido.empresa_envio == "Via Cargo"


def test_no_aplica_si_no_hay_nombre():
    pedido = SimpleNamespace()

    ok = aplicar_sucursal_elegida_al_pedido(
        pedido,
        {"direccion": "Sin nombre"},
        transporte="Via Cargo",
    )

    assert ok is False



def test_marca_resumen_sucursal_confirmada():
    from services.workflow_logistica_sucursal import marca_resumen_sucursal_confirmada

    marca = marca_resumen_sucursal_confirmada(
        1,
        {"nombre": "Terminal Formosa Boleteria 5"},
    )

    assert marca == "Sucursal confirmada por opción 2: Terminal Formosa Boleteria 5"


def test_agrega_marca_resumen_sucursal_confirmada_una_sola_vez():
    from services.workflow_logistica_sucursal import agregar_marca_resumen_sucursal_confirmada

    resumen = "Datos completos"
    sucursal = {"nombre": "Terminal Formosa Boleteria 5"}

    nuevo = agregar_marca_resumen_sucursal_confirmada(resumen, 1, sucursal)
    repetido = agregar_marca_resumen_sucursal_confirmada(nuevo, 1, sucursal)

    assert nuevo == "Datos completos | Sucursal confirmada por opción 2: Terminal Formosa Boleteria 5"
    assert repetido == nuevo


def test_no_agrega_marca_si_faltan_datos():
    from services.workflow_logistica_sucursal import agregar_marca_resumen_sucursal_confirmada

    assert agregar_marca_resumen_sucursal_confirmada("Datos completos", None, {"nombre": "X"}) == "Datos completos"
    assert agregar_marca_resumen_sucursal_confirmada("Datos completos", 1, {}) == "Datos completos"
