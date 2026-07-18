from services.workflow_correo_sucursal_oferta import (
    armar_mensaje_sucursales_correo,
    ids_sucursales_correo_oferta,
    normalizar_sucursal_correo_oferta,
    preparar_oferta_sucursales_correo,
    seleccionar_sucursales_correo_oferta,
)


def test_normaliza_sucursal_correo_oferta():
    sucursal = {
        "agencyId": "ag-1",
        "name": "Correo Centro",
        "address": "San Martin 123",
        "city": "Viedma",
        "province": "Rio Negro",
        "postalCode": "8500",
    }

    datos = normalizar_sucursal_correo_oferta(sucursal)

    assert datos["id"] == "ag-1"
    assert datos["nombre"] == "Correo Centro"
    assert datos["direccion"] == "San Martin 123"
    assert datos["localidad"] == "Viedma"
    assert datos["provincia"] == "Rio Negro"
    assert datos["cp"] == "8500"
    assert datos["raw"] == sucursal


def test_selecciona_limite_de_sucursales():
    sucursales = [
        {"id": "1", "nombre": "Uno"},
        {"id": "2", "nombre": "Dos"},
        {"id": "3", "nombre": "Tres"},
        {"id": "4", "nombre": "Cuatro"},
    ]

    seleccionadas = seleccionar_sucursales_correo_oferta(sucursales, limite=2)

    assert [s["id"] for s in seleccionadas] == ["1", "2"]


def test_ids_sucursales_correo_oferta():
    sucursales = [
        {"agencyId": "a1", "name": "Uno"},
        {"codigo": "c2", "descripcion": "Dos"},
        {"nombre": "Sin id"},
    ]

    assert ids_sucursales_correo_oferta(sucursales) == ["a1", "c2", "3"]


def test_arma_mensaje_sucursales_correo():
    mensaje = armar_mensaje_sucursales_correo([
        {
            "id": "1",
            "nombre": "Correo Centro",
            "direccion": "San Martin 123",
            "localidad": "Viedma",
        },
        {
            "id": "2",
            "nombre": "Correo Norte",
            "direccion": "Belgrano 456",
            "localidad": "Patagones",
        },
    ])

    assert "Genial, ya tenemos los datos" in mensaje
    assert "1) Correo Centro" in mensaje
    assert "San Martin 123 - Viedma" in mensaje
    assert "2) Correo Norte" in mensaje
    assert "Decime cuál preferís" in mensaje


def test_preparar_oferta_sucursales_correo():
    oferta = preparar_oferta_sucursales_correo(
        [
            {"agencyId": "a1", "name": "Correo Centro", "address": "San Martin 123"},
            {"agencyId": "a2", "name": "Correo Norte", "address": "Belgrano 456"},
        ],
        limite=1,
    )

    assert oferta is not None
    assert len(oferta.sucursales) == 1
    assert oferta.ids == ["a1"]
    assert "Correo Centro" in oferta.mensaje


def test_preparar_oferta_sin_sucursales_devuelve_none():
    assert preparar_oferta_sucursales_correo([], limite=3) is None



def test_aplica_oferta_correo_al_pedido_por_ml():
    from types import SimpleNamespace
    from services.workflow_correo_sucursal_oferta import aplicar_oferta_sucursales_correo_al_pedido

    pedido = SimpleNamespace(
        correo_sucursales_ofrecidas="",
        ia_sucursales_ofrecidas="",
        empresa_envio="",
        tipo_entrega="",
        wa_estado="falta_elegir_transporte",
        wa_ultimo_contacto="valor-previo",
    )

    ok = aplicar_oferta_sucursales_correo_al_pedido(
        pedido,
        [{"agencyId": "a1", "name": "Correo Centro"}],
        ["a1"],
        canal_origen="ml",
    )

    assert ok is True
    assert "Correo Centro" in pedido.correo_sucursales_ofrecidas
    assert pedido.empresa_envio == "Correo Argentino"
    assert pedido.tipo_entrega == "Sucursal"
    assert pedido.wa_estado == ""
    assert pedido.wa_ultimo_contacto is None


def test_aplica_oferta_correo_al_pedido_por_whatsapp():
    from datetime import datetime
    from types import SimpleNamespace
    from services.workflow_correo_sucursal_oferta import aplicar_oferta_sucursales_correo_al_pedido

    ahora = datetime(2026, 1, 2, 3, 4, 5)
    pedido = SimpleNamespace(
        correo_sucursales_ofrecidas="",
        empresa_envio="",
        tipo_entrega="",
        wa_estado="",
        wa_ultimo_contacto=None,
    )

    ok = aplicar_oferta_sucursales_correo_al_pedido(
        pedido,
        [{"agencyId": "a1", "name": "Correo Centro"}],
        ["a1"],
        canal_origen="wa",
        ahora_fn=lambda: ahora,
    )

    assert ok is True
    assert pedido.wa_estado == "falta_elegir_transporte"
    assert pedido.wa_ultimo_contacto == ahora


def test_aplica_oferta_correo_fallback_ia_sucursales_si_no_existe_campo_correo():
    from types import SimpleNamespace
    from services.workflow_correo_sucursal_oferta import aplicar_oferta_sucursales_correo_al_pedido

    pedido = SimpleNamespace(
        ia_sucursales_ofrecidas="",
        empresa_envio="",
        tipo_entrega="",
        wa_estado="",
        wa_ultimo_contacto=None,
    )

    ok = aplicar_oferta_sucursales_correo_al_pedido(
        pedido,
        [{"agencyId": "a1", "name": "Correo Centro"}],
        ["a1"],
        canal_origen="ml",
    )

    assert ok is True
    assert pedido.ia_sucursales_ofrecidas == "[\"a1\"]"


def test_no_aplica_oferta_correo_sin_sucursales():
    from types import SimpleNamespace
    from services.workflow_correo_sucursal_oferta import aplicar_oferta_sucursales_correo_al_pedido

    pedido = SimpleNamespace()

    assert aplicar_oferta_sucursales_correo_al_pedido(pedido, [], []) is False


def test_resultado_preparacion_oferta_correo_preparada():
    from services.workflow_correo_sucursal_oferta import (
        ResultadoPreparacionOfertaCorreo,
    )

    resultado = ResultadoPreparacionOfertaCorreo.preparada(
        "Elegí una sucursal",
    )

    assert resultado.ok is True
    assert resultado.escalada is False
    assert resultado.estado == "preparada"
    assert resultado.mensaje == "Elegí una sucursal"
    assert resultado.requiere_persistencia is True


def test_resultado_preparacion_oferta_correo_sin_oferta():
    from services.workflow_correo_sucursal_oferta import (
        ResultadoPreparacionOfertaCorreo,
    )

    resultado = ResultadoPreparacionOfertaCorreo.sin_oferta(
        "feature deshabilitada",
    )

    assert resultado.ok is False
    assert resultado.escalada is False
    assert resultado.estado == "sin_oferta"
    assert resultado.motivo == "feature deshabilitada"
    assert resultado.requiere_persistencia is False


def test_resultado_preparacion_oferta_correo_escalada():
    from services.workflow_correo_sucursal_oferta import (
        ResultadoPreparacionOfertaCorreo,
    )

    resultado = ResultadoPreparacionOfertaCorreo.escalada_por(
        "requiere operador",
    )

    assert resultado.ok is False
    assert resultado.escalada is True
    assert resultado.estado == "escalada"
    assert resultado.motivo == "requiere operador"
    assert resultado.requiere_persistencia is False
