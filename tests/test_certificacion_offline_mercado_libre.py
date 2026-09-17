import json
from pathlib import Path

import pytest

from services.certificacion_offline_mercado_libre import (
    EFECTOS_BLOQUEADOS, certificar_publicaciones_offline, exportar_json,
    normalizar_publicacion, procesar_documento_publicaciones,
)


BASE = {"id": "MLA100", "seller_sku": "SKU-1", "price": 1000, "commission_percentage": 15, "fixed_fee": 100, "shipping_cost": 0, "economic_floor": 700}


def test_liquidacion_respeta_comision_cargo_envio_y_piso():
    fila = normalizar_publicacion({**BASE, "shipping_cost": 50}, cuenta_codigo="A", organizacion_id=2, unidad_negocio_id=3)
    assert fila["comision_centavos"] == 15000
    assert fila["cargo_fijo_centavos"] == 10000
    assert fila["envio_centavos"] == 5000
    assert fila["liquidacion_centavos"] == 70000
    assert fila["cumple_piso"] is True


def test_liquidacion_admite_publicidad_cuotas_y_devoluciones_explicitas():
    fila = normalizar_publicacion(
        {**BASE, "publicidad_pct": 10, "financing_percentage": 6, "returns_cost": 40},
        cuenta_codigo="A", organizacion_id=2, unidad_negocio_id=3,
    )
    assert fila["publicidad_centavos"] == 10000
    assert fila["financiacion_centavos"] == 6000
    assert fila["devoluciones_centavos"] == 4000
    assert fila["liquidacion_centavos"] == 55000
    assert all(fila["componentes_informados"].values())


def test_promocion_exige_cancelacion_antes_del_precio():
    fila = normalizar_publicacion({**BASE, "economic_floor": 900, "proposed_safe_price": 1200, "promotion_active": True}, cuenta_codigo="A", organizacion_id=2, unidad_negocio_id=3)
    assert [x["accion"] for x in fila["acciones_proyectadas"]] == ["cancelar_promocion_manual", "actualizar_precio_manual"]
    assert fila["acciones_proyectadas"][1]["depende_de"] == "cancelar_promocion_manual"
    assert all(x["ejecutada"] is False for x in fila["acciones_proyectadas"])


def test_documento_rechaza_duplicados_y_conserva_tenant():
    resultado = procesar_documento_publicaciones(json.dumps([BASE, BASE]), cuenta_codigo="CTA", organizacion_id=8, unidad_negocio_id=9)
    assert resultado["resumen"] == {"filas": 2, "validas": 1, "errores": 1, "rentables": 1, "debajo_piso": 0, "promociones_riesgosas": 0, "acciones_proyectadas": 0}
    assert resultado["resultados"][0]["organizacion_id"] == 8
    assert resultado["resultados"][0]["unidad_negocio_id"] == 9


def test_validaciones_y_evidencia_determinista():
    with pytest.raises(ValueError):
        normalizar_publicacion({**BASE, "commission_percentage": 100}, cuenta_codigo="A", organizacion_id=1, unidad_negocio_id=1)
    primero = procesar_documento_publicaciones(BASE, cuenta_codigo="A", organizacion_id=1, unidad_negocio_id=1)
    segundo = procesar_documento_publicaciones(BASE, cuenta_codigo="A", organizacion_id=1, unidad_negocio_id=1)
    assert primero["firma_evidencia"] == segundo["firma_evidencia"]
    assert json.loads(exportar_json(primero).getvalue().decode("utf-8"))["modo"] == "mercado_libre_offline"


def test_certificacion_cubre_cuatro_escenarios():
    resultado = certificar_publicaciones_offline()
    assert resultado["aprobada"] is True
    assert resultado["aprobados"] == resultado["total"] == 4
    assert not any(EFECTOS_BLOQUEADOS.values())


def test_panel_es_tenant_y_no_toca_importador_productivo():
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    panel = Path("templates/admin_mercado_libre_offline.html").read_text(encoding="utf-8")
    assert "/admin/comercial/mercado-libre-offline" in rutas
    assert "organizacion_id=organizacion.id" in rutas
    assert "unidad_negocio_id=unidad_activa.id" in rutas
    assert "MERCADO LIBRE DESCONECTADO" in panel
    productivo = Path("services/ml_importacion.py").read_text(encoding="utf-8")
    assert "certificacion_offline_mercado_libre" not in productivo


def test_servicio_no_tiene_transporte_credenciales_ni_persistencia():
    fuente = Path("services/certificacion_offline_mercado_libre.py").read_text(encoding="utf-8").lower()
    for prohibido in ("requests", "urlopen", "db.session", "commit(", "access_token", "client_secret", "http://", "https://"):
        assert prohibido not in fuente
