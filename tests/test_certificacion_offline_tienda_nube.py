import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.certificacion_offline_tienda_nube import (
    certificar_escenarios_tienda_nube,
    exportar_diagnostico_tienda_nube,
    procesar_fixture_tienda_nube,
    resolver_cuenta_tenant,
)


def vinculo(**cambios):
    cuenta = SimpleNamespace(id=8, store_id="STORE-1")
    datos = dict(
        id=4, organizacion_id=2, unidad_negocio_id=3,
        estado="activo", canal="tienda_nube",
        tienda_nube_cuenta_id=8, tienda_nube_cuenta=cuenta,
    )
    datos.update(cambios)
    return SimpleNamespace(**datos)


def pedido(**cambios):
    datos = dict(
        id=100, number="N100", total="1250.50", status="open",
        payment_status="paid", store_id="STORE-1",
        contact_phone="2920123456",
        products=[{"sku": "pp6040h", "name": "Parrilla", "quantity": 1}],
    )
    datos.update(cambios)
    return datos


def procesar(datos):
    return procesar_fixture_tienda_nube(
        json.dumps(datos), vinculo(), organizacion_id=2, unidad_negocio_id=3,
    )


def test_resuelve_cuenta_activa_exacta_del_tenant():
    contexto = resolver_cuenta_tenant(vinculo(), organizacion_id=2, unidad_negocio_id=3)
    assert contexto == {
        "vinculo_id": 4, "cuenta_id": 8, "store_id": "STORE-1",
        "organizacion_id": 2, "unidad_negocio_id": 3,
    }


def test_bloquea_vinculo_ajeno_inactivo_o_sin_store():
    casos = [
        vinculo(organizacion_id=9), vinculo(unidad_negocio_id=9),
        vinculo(estado="desactivado"),
        vinculo(tienda_nube_cuenta=SimpleNamespace(id=8, store_id="")),
    ]
    for caso in casos:
        with pytest.raises(ValueError):
            resolver_cuenta_tenant(caso, organizacion_id=2, unidad_negocio_id=3)


def test_normaliza_pedido_pagado_sin_escribir():
    resultado = procesar([pedido()])
    fila = resultado["resultados"][0]
    assert fila["identidad"] == "STORE-1:100"
    assert fila["total_centavos"] == 125050
    assert fila["productos"][0]["sku"] == "PP6040H"
    assert fila["apto_importacion_simulada"]
    assert resultado["escrituras"] == resultado["resumen"]["acciones_externas"] == 0


def test_bloquea_impago_cancelado_enviado_y_producto_sin_sku():
    datos = pedido(
        payment_status="pending", status="cancelled",
        shipping_status="shipped", products=[{"name": "Sin SKU"}],
    )
    fila = procesar([datos])["resultados"][0]
    assert set(fila["bloqueos"]) == {
        "pedido_cancelado", "pago_no_confirmado",
        "pedido_ya_enviado", "producto_sin_sku",
    }
    assert not fila["apto_importacion_simulada"]


def test_rechaza_store_ajeno_y_duplicados_en_archivo():
    resultado = procesar([pedido(store_id="OTRO"), pedido(), pedido()])
    assert resultado["resumen"]["validas"] == 1
    assert resultado["resumen"]["errores"] == 2
    assert any("otro store_id" in error["error"] for error in resultado["errores"])
    assert any("duplicado" in error["error"] for error in resultado["errores"])


def test_certificacion_cubre_cinco_escenarios():
    resultado = certificar_escenarios_tienda_nube()
    assert resultado["aprobada"] and len(resultado["casos"]) == 5
    assert resultado["acciones_externas"] == resultado["escrituras"] == 0


def test_exportacion_es_json_utf8():
    contenido = exportar_diagnostico_tienda_nube({"detalle": "diagnóstico"}).getvalue()
    assert json.loads(contenido.decode("utf-8"))["detalle"] == "diagnóstico"


def test_panel_filtra_por_tenant_y_no_persiste():
    ruta = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    html = Path("templates/admin_tienda_nube_offline.html").read_text(encoding="utf-8")
    bloque = ruta.split("def tienda_nube_offline_comercial():", 1)[1].split("\n    @blueprint.route", 1)[0]
    assert "organizacion_id=organizacion.id" in bloque
    assert "unidad_negocio_id=unidad_activa.id" in bloque
    assert "db.session" not in bloque
    assert "No consulta la tienda" in html and "Acciones externas" in html


def test_servicio_no_contiene_transporte_credenciales_ni_persistencia():
    fuente = Path("services/certificacion_offline_tienda_nube.py").read_text(encoding="utf-8").lower()
    prohibidos = (
        "db.session", "requests", "urlopen", "access_token", "client_secret",
        "http://", "https://", ".commit(", ".rollback(", ".add(", ".delete(",
    )
    assert not any(texto in fuente for texto in prohibidos)
