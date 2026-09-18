import json
from pathlib import Path
from types import SimpleNamespace

from services.certificacion_offline_tienda_nube import procesar_fixture_tienda_nube


def _vinculo():
    cuenta = SimpleNamespace(id=8, store_id="STORE-1")
    return SimpleNamespace(
        id=4, organizacion_id=2, unidad_negocio_id=3, estado="activo",
        canal="tienda_nube", tienda_nube_cuenta_id=8,
        tienda_nube_cuenta=cuenta,
    )


def _control(sku="SKU-1"):
    regla = SimpleNamespace(
        lista_precio_id=10, comision_pct=5, publicidad_pct=2,
        financiacion_pct=3, devoluciones_pct=4,
        umbral_envio_centavos=0, costo_envio_default_centavos=0,
        tramos=(),
    )
    costo = SimpleNamespace(producto=SimpleNamespace(sku=sku))
    return {
        "regla_canal": regla, "costo": costo,
        "minimo": {"piso_liquidacion_centavos": 80000},
    }


def _pedido(productos):
    return {
        "id": 100, "store_id": "STORE-1", "total": 1000,
        "payment_status": "paid", "products": productos,
    }


def test_controla_pedido_con_el_motor_integral_del_canal():
    salida = procesar_fixture_tienda_nube(
        json.dumps(_pedido([{"sku": "SKU-1", "quantity": 1, "price": 1000}])),
        _vinculo(), organizacion_id=2, unidad_negocio_id=3,
        controles=[_control()],
    )
    control = salida["resultados"][0]["control_economico"]
    assert control["liquidacion_estimada_centavos"] == 86000
    assert control["piso_minimo_centavos"] == 80000
    assert control["estado"] == "rentable"
    assert salida["resumen"]["rentables"] == 1


def test_bloquea_sku_ambiguo_ausente_o_precio_no_informado():
    casos = (
        ([_control("OTRO")], "control_interno_ausente"),
        ([_control(), _control()], "control_interno_ambiguo"),
        ([_control()], "precio_unitario_no_informado"),
    )
    for controles, bloqueo in casos:
        producto = {"sku": "SKU-1", "quantity": 1}
        if bloqueo != "precio_unitario_no_informado":
            producto["price"] = 1000
        salida = procesar_fixture_tienda_nube(
            json.dumps(_pedido([producto])), _vinculo(),
            organizacion_id=2, unidad_negocio_id=3, controles=controles,
        )
        control = salida["resultados"][0]["control_economico"]
        assert control["estado"] == "bloqueada"
        assert bloqueo in control["bloqueos"][0]
        assert control["acciones_externas"] == 0


def test_ruta_inyecta_solo_control_del_tenant_activo():
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    bloque = rutas.split("def tienda_nube_offline_comercial():", 1)[1].split("\n    @blueprint.route", 1)[0]
    assert "obtener_datos_panel_comercial" in bloque
    assert 'controles=datos_panel_tn["control_comercial"]' in bloque
    assert "organizacion.id" in bloque and "unidad_activa.id" in bloque


def test_panel_explica_control_sin_habilitar_acciones():
    panel = Path("templates/admin_tienda_nube_offline.html").read_text(encoding="utf-8")
    assert "Control económico" in panel
    assert "Economía bloqueada" in panel
    servicio = Path("services/certificacion_offline_tienda_nube.py").read_text(encoding="utf-8").lower()
    for prohibido in ("requests", "urlopen", "access_token", "client_secret", "db.session"):
        assert prohibido not in servicio
