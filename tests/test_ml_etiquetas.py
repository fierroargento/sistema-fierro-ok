import json
import os

from services.ml_etiquetas import (
    ml_guardar_etiqueta_pdf_service,
    ml_preparar_etiqueta_mercado_envios_service,
)


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


def test_ml_preparar_etiqueta_mercado_envios_service_usa_shipping_de_order():
    resultado = ml_preparar_etiqueta_mercado_envios_service(
        {"shipping": {"id": "111"}},
        ml_guardar_etiqueta_pdf=lambda shipping_id: f"ml_{shipping_id}.pdf",
    )

    assert resultado == "ml_111.pdf"
