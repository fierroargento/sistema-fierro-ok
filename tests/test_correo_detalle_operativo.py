from types import SimpleNamespace

from services.correo_detalle_operativo import detalle_operativo_correo_pedido


def pedido_fake(**kwargs):
    base = {
        "empresa_envio": "Correo Argentino",
        "tipo_entrega": "Sucursal",
        "costo_envio": 7500,
        "costo_envio_sucursal": 7500,
        "costo_envio_domicilio": 12000,
        "correo_sucursales_ofrecidas": """
        [
          {
            "id": "TA001",
            "nombre": "TRES ARROYOS",
            "direccion": "Av. Belgrano 123",
            "localidad": "Tres Arroyos",
            "provincia": "Buenos Aires",
            "cp": "7500",
            "distancia_km": 62.4
          }
        ]
        """,
        "sucursal_nombre": "TRES ARROYOS",
        "direccion": "",
        "localidad": "Claromeco",
        "provincia": "Buenos Aires",
        "codigo_postal": "7505",
        "ia_resumen": "TRANSPORTE: Correo Argentino sucursal priorizado por costo ($7500)",
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def preferencias_fake():
    return {
        "max_costo_correo_sucursal_acordas": 8000,
        "max_costo_correo_sucursal_pp6040": 10000,
        "requiere_operador_para_pago_etiqueta": True,
        "priorizar_correo_sucursal_acordas": True,
    }


def test_detalle_correo_expone_costos_y_umbrales():
    detalle = detalle_operativo_correo_pedido(
        pedido_fake(),
        preferencias=preferencias_fake(),
    )

    assert detalle["es_correo"] is True
    assert detalle["costo_sucursal"] == 7500
    assert detalle["costo_domicilio"] == 12000
    assert detalle["umbral_acordas"] == 8000
    assert detalle["requiere_operador_para_pago_etiqueta"] is True


def test_detalle_correo_expone_sucursal_elegida_y_ofrecidas():
    detalle = detalle_operativo_correo_pedido(
        pedido_fake(),
        preferencias=preferencias_fake(),
    )

    assert len(detalle["sucursales_ofrecidas"]) == 1
    assert detalle["sucursal_elegida"]["nombre"] == "TRES ARROYOS"
    assert detalle["sucursal_elegida"]["direccion"] == "Av. Belgrano 123"
    assert detalle["sucursal_elegida"]["distancia_km"] == 62.4


def test_detalle_correo_fallback_sucursal_pedido_si_no_matchea_ofrecida():
    detalle = detalle_operativo_correo_pedido(
        pedido_fake(
            correo_sucursales_ofrecidas="[]",
            sucursal_nombre="Sucursal cargada manual",
            direccion="Calle 1",
        ),
        preferencias=preferencias_fake(),
    )

    assert detalle["sucursal_elegida"]["nombre"] == "Sucursal cargada manual"
    assert detalle["sucursal_elegida"]["direccion"] == "Calle 1"


def test_detalle_no_correo_sin_datos_no_muestra_panel():
    detalle = detalle_operativo_correo_pedido(
        pedido_fake(
            empresa_envio="Vía Cargo",
            costo_envio=None,
            costo_envio_sucursal=None,
            costo_envio_domicilio=None,
            correo_sucursales_ofrecidas="[]",
            sucursal_nombre="",
            ia_resumen="",
        ),
        preferencias=preferencias_fake(),
    )

    assert detalle["es_correo"] is False
    assert detalle["tiene_datos"] is False
