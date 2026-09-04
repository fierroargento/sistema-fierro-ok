import json
from pathlib import Path

from services.adaptadores_offline_canales import adaptar_documento, adaptar_fixture


def test_publicacion_ml_separa_precio_comision_envio_y_promocion():
    eventos = adaptar_fixture("mercado_libre", "publicacion", {
        "id": "MLA-1", "price": 1000, "original_price": 1100,
        "status": "active", "listing_type_id": "gold_special",
        "sale_fee_amount": 150, "shipping": {"free_shipping": True, "mode": "me2"},
    }, cuenta_codigo="CUENTA-ML")
    assert [evento["tipo"] for evento in eventos] == ["publicacion", "comision", "envio", "promocion"]
    assert eventos[0]["datos"]["precio_centavos"] == 100000
    assert eventos[-1]["datos"]["descuento_pct"] == "9.09"


def test_venta_ml_normaliza_items_variantes_y_centavos():
    eventos = adaptar_fixture("mercado_libre", "venta", {
        "id": 22, "status": "paid", "paid_amount": 3000, "date_created": "2026-09-04T10:00:00",
        "order_items": [{"item": {"id": "MLA-1", "variation_id": 7, "seller_sku": "SKU-1"}, "quantity": 2, "unit_price": 1500}],
    }, cuenta_codigo="CUENTA-ML")
    datos = eventos[0]["datos"]
    assert datos["items"][0] == {"referencia_item": "MLA-1", "variante_id": 7, "sku": "SKU-1", "cantidad": 2, "precio_unitario_centavos": 150000}


def test_pago_mp_conserva_bruto_neto_comisiones_y_venta():
    evento = adaptar_fixture("mercado_pago", "pago", {
        "id": 50, "external_reference": "VENTA-22", "transaction_amount": 3000,
        "transaction_details": {"net_received_amount": 2500},
        "fee_details": [{"amount": 300}, {"amount": 200}], "status": "approved",
    }, cuenta_codigo="CUENTA-MP")[0]
    assert evento["datos"]["bruto_centavos"] == 300000
    assert evento["datos"]["neto_centavos"] == 250000
    assert evento["datos"]["comisiones_centavos"] == 50000


def test_venta_tn_genera_venta_envio_y_promocion():
    eventos = adaptar_fixture("tienda_nube", "venta", {
        "id": 80, "total": 5000, "payment_status": "paid", "shipping_cost_customer": 600,
        "discount_coupon": 200, "products": [{"id": 1, "variant_id": 2, "sku": "SKU-TN", "quantity": 1, "price": 4600}],
    }, cuenta_codigo="TIENDA-1")
    assert [evento["tipo"] for evento in eventos] == ["envio", "promocion", "venta"]


def test_documento_por_lote_aisla_fixtures_invalidos():
    documento = json.dumps([
        {"id": 1, "transaction_amount": 1000, "external_reference": "V-1", "net_received_amount": 900},
        {"id": 2},
    ]).encode("utf-8")
    resultado = adaptar_documento("mercado_pago", "pago", documento, cuenta_codigo="MP-1")
    assert resultado["total_fixtures"] == 2
    assert len(resultado["eventos"]) == 1 and len(resultado["errores"]) == 1


def test_referencias_y_huellas_permiten_idempotencia():
    payload = {"id": "D-1", "order_id": "V-1", "amount": 100, "status": "approved"}
    primero = adaptar_fixture("mercado_pago", "devolucion", payload, cuenta_codigo="MP-1")[0]
    segundo = adaptar_fixture("mercado_pago", "devolucion", payload, cuenta_codigo="MP-1")[0]
    assert primero["referencia"] == segundo["referencia"] == "D-1:devolucion"
    assert primero["datos"]["origen_fixture_hash"] == segundo["datos"]["origen_fixture_hash"]


def test_adaptadores_solo_leen_archivos_y_no_tienen_transporte():
    servicio = Path("services/adaptadores_offline_canales.py").read_text(encoding="utf-8").lower()
    panel = Path("templates/admin_adaptadores_offline.html").read_text(encoding="utf-8")
    rutas = Path("modules/admin/comercial/routes.py").read_text(encoding="utf-8")
    assert "/admin/comercial/adaptadores-offline" in rutas
    assert "Solo archivos locales" in panel and "no usa credenciales" in panel
    for prohibido in ("requests", "oauth", "webhook", "access_token", "http://", "https://"):
        assert prohibido not in servicio
