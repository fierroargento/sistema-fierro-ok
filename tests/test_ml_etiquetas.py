import json
import os
from types import SimpleNamespace

from services.ml_etiquetas import (
    etiqueta_archivo_local_disponible_service,
    ml_asegurar_etiqueta_disponible_service,
    ml_guardar_etiqueta_pdf_service,
    ml_preparar_etiqueta_mercado_envios_service,
)


def test_etiqueta_archivo_local_disponible_service_rechaza_vacio(tmp_path):
    assert etiqueta_archivo_local_disponible_service("", tmp_path) is False
    assert etiqueta_archivo_local_disponible_service(None, tmp_path) is False


def test_etiqueta_archivo_local_disponible_service_detecta_archivo(tmp_path):
    archivo = tmp_path / "ml_123.pdf"
    archivo.write_bytes(b"%PDF")

    assert etiqueta_archivo_local_disponible_service("ml_123.pdf", tmp_path) is True


def test_etiqueta_archivo_local_disponible_service_usa_basename(tmp_path):
    archivo = tmp_path / "ml_segura.pdf"
    archivo.write_bytes(b"%PDF")

    assert etiqueta_archivo_local_disponible_service("../ml_segura.pdf", tmp_path) is True


def test_ml_guardar_etiqueta_pdf_devuelve_none_sin_shipping_id(tmp_path):
    resultado = ml_guardar_etiqueta_pdf_service(
        "",
        tmp_path,
        lambda nombre: nombre,
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no debe llamar API")),
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no debe descargar URL")),
    )

    assert resultado is None


def test_ml_guardar_etiqueta_pdf_reutiliza_archivo_existente(tmp_path):
    archivo = tmp_path / "ml_123.pdf"
    archivo.write_bytes(b"%PDF existente")

    resultado = ml_guardar_etiqueta_pdf_service(
        "123",
        tmp_path,
        lambda nombre: nombre,
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no debe llamar API")),
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no debe descargar URL")),
    )

    assert resultado == "ml_123.pdf"


def test_ml_guardar_etiqueta_pdf_guarda_binario_pdf(tmp_path):
    llamadas = []

    def ml_api_get_binario(endpoint, params=None, accept=None):
        llamadas.append((endpoint, params, accept))
        return b"%PDF contenido", "application/pdf"

    resultado = ml_guardar_etiqueta_pdf_service(
        "456",
        tmp_path,
        lambda nombre: nombre,
        ml_api_get_binario,
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no debe descargar URL")),
    )

    assert resultado == "ml_456.pdf"
    assert (tmp_path / "ml_456.pdf").read_bytes() == b"%PDF contenido"
    assert llamadas == [
        (
            "/shipment_labels",
            {"shipment_ids": "456", "response_type": "pdf"},
            "application/pdf",
        )
    ]


def test_ml_guardar_etiqueta_pdf_usa_url_si_ml_devuelve_json(tmp_path):
    payload = {
        "results": [
            {"url": "https://example.com/etiqueta.pdf"}
        ]
    }

    def ml_api_get_binario(endpoint, params=None, accept=None):
        return json.dumps(payload).encode("utf-8"), "application/json"

    def asegurar_pdf_local_desde_url(url, prefijo=None):
        assert url == "https://example.com/etiqueta.pdf"
        assert prefijo == "ml"
        return os.path.join(str(tmp_path), "ml_descargada.pdf")

    resultado = ml_guardar_etiqueta_pdf_service(
        "789",
        tmp_path,
        lambda nombre: nombre,
        ml_api_get_binario,
        asegurar_pdf_local_desde_url,
    )

    assert resultado == "ml_descargada.pdf"


def test_ml_asegurar_etiqueta_disponible_service_no_bloquea_no_mercado_envios():
    pedido = SimpleNamespace(etiqueta_archivo=None)

    resultado = ml_asegurar_etiqueta_disponible_service(
        pedido,
        es_mercado_envios_fn=lambda pedido: False,
        etiqueta_archivo_local_disponible_fn=lambda archivo: (_ for _ in ()).throw(AssertionError("no debe validar archivo")),
        ml_obtener_order_fn=lambda id_venta: (_ for _ in ()).throw(AssertionError("no debe buscar order")),
        ml_guardar_etiqueta_pdf_fn=lambda shipping_id: (_ for _ in ()).throw(AssertionError("no debe descargar etiqueta")),
    )

    assert resultado is True


def test_ml_asegurar_etiqueta_disponible_service_acepta_url_existente():
    pedido = SimpleNamespace(etiqueta_archivo="https://example.com/etiqueta.pdf")

    resultado = ml_asegurar_etiqueta_disponible_service(
        pedido,
        es_mercado_envios_fn=lambda pedido: True,
        etiqueta_archivo_local_disponible_fn=lambda archivo: (_ for _ in ()).throw(AssertionError("no debe validar archivo")),
        ml_obtener_order_fn=lambda id_venta: (_ for _ in ()).throw(AssertionError("no debe buscar order")),
        ml_guardar_etiqueta_pdf_fn=lambda shipping_id: (_ for _ in ()).throw(AssertionError("no debe descargar etiqueta")),
    )

    assert resultado is True


def test_ml_asegurar_etiqueta_disponible_service_acepta_archivo_local_existente():
    pedido = SimpleNamespace(etiqueta_archivo="ml_123.pdf")

    resultado = ml_asegurar_etiqueta_disponible_service(
        pedido,
        es_mercado_envios_fn=lambda pedido: True,
        etiqueta_archivo_local_disponible_fn=lambda archivo: archivo == "ml_123.pdf",
        ml_obtener_order_fn=lambda id_venta: (_ for _ in ()).throw(AssertionError("no debe buscar order")),
        ml_guardar_etiqueta_pdf_fn=lambda shipping_id: (_ for _ in ()).throw(AssertionError("no debe descargar etiqueta")),
    )

    assert resultado is True


def test_ml_asegurar_etiqueta_disponible_service_recupera_shipping_y_descarga():
    pedido = SimpleNamespace(
        id_venta="ORDER123",
        ml_shipping_id="",
        etiqueta_archivo="",
    )

    resultado = ml_asegurar_etiqueta_disponible_service(
        pedido,
        es_mercado_envios_fn=lambda pedido: True,
        etiqueta_archivo_local_disponible_fn=lambda archivo: archivo == "ml_999.pdf",
        ml_obtener_order_fn=lambda id_venta: {"shipping": {"id": "999"}},
        ml_guardar_etiqueta_pdf_fn=lambda shipping_id: f"ml_{shipping_id}.pdf",
    )

    assert resultado is True
    assert pedido.ml_shipping_id == "999"
    assert pedido.etiqueta_archivo == "ml_999.pdf"


def test_ml_asegurar_etiqueta_disponible_service_devuelve_false_si_no_descarga():
    pedido = SimpleNamespace(
        id_venta="ORDER123",
        ml_shipping_id="999",
        etiqueta_archivo="",
    )

    resultado = ml_asegurar_etiqueta_disponible_service(
        pedido,
        es_mercado_envios_fn=lambda pedido: True,
        etiqueta_archivo_local_disponible_fn=lambda archivo: False,
        ml_obtener_order_fn=lambda id_venta: {"shipping": {"id": "999"}},
        ml_guardar_etiqueta_pdf_fn=lambda shipping_id: None,
    )

    assert resultado is False
    assert pedido.etiqueta_archivo == ""


def test_ml_preparar_etiqueta_mercado_envios_service_usa_shipping_de_order():
    resultado = ml_preparar_etiqueta_mercado_envios_service(
        {"shipping": {"id": "111"}},
        ml_guardar_etiqueta_pdf=lambda shipping_id: f"ml_{shipping_id}.pdf",
    )

    assert resultado == "ml_111.pdf"
