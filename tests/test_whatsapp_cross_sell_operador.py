import types

from domain.estados import Estado
from modules.whatsapp.cross_sell_operador import (
    ESTADOS_SIN_CROSS_SELL,
    _url_publica,
)


def test_estados_sin_cross_sell_incluye_despachado_y_posteriores():
    assert Estado.DESPACHADO in ESTADOS_SIN_CROSS_SELL
    assert Estado.VERIFICAR_DESTINO in ESTADOS_SIN_CROSS_SELL
    assert Estado.LISTO_RETIRAR in ESTADOS_SIN_CROSS_SELL
    assert Estado.DEMORA in ESTADOS_SIN_CROSS_SELL
    assert Estado.RECLAMO in ESTADOS_SIN_CROSS_SELL
    assert Estado.NO_ENTREGADO in ESTADOS_SIN_CROSS_SELL
    assert Estado.ENTREGADO in ESTADOS_SIN_CROSS_SELL
    assert Estado.FINALIZADO in ESTADOS_SIN_CROSS_SELL
    assert Estado.CANCELADO in ESTADOS_SIN_CROSS_SELL
    assert Estado.RECLAMAR_ML in ESTADOS_SIN_CROSS_SELL


def test_url_publica_respeta_url_absoluta():
    url = "https://example.com/static/catalogo/productos/KPADES/wa.jpg"

    assert _url_publica(url, "https://sistema.test") == url


def test_url_publica_convierte_ruta_relativa_en_url_publica():
    assert (
        _url_publica(
            "/static/catalogo/productos/KPADES/wa.jpg",
            "https://sistema.test/"
        )
        == "https://sistema.test/static/catalogo/productos/KPADES/wa.jpg"
    )


def test_url_publica_vacia_devuelve_vacio():
    assert _url_publica("", "https://sistema.test/") == ""
    assert _url_publica(None, "https://sistema.test/") == ""

import json
from pathlib import Path


def test_catalogo_cross_sell_imagenes_son_https():
    catalogo_path = Path("static/catalogo/catalogo_config.json")
    data = json.loads(catalogo_path.read_text(encoding="utf-8"))

    productos = data.get("productos", {})

    for sku in ["KPADES", "BPPC01", "KITPACH", "B4030H", "B5030H"]:
        imagen_url = productos.get(sku, {}).get("imagen_url", "")
        assert imagen_url.startswith("https://"), f"{sku} no tiene imagen_url HTTPS"

from modules.whatsapp.cross_sell_operador import _armar_texto_propuesta_cross_sell


def test_texto_cross_sell_pp6040h_es_especifico():
    texto = _armar_texto_propuesta_cross_sell([
        {"sku": "KPADES", "nombre": "Kit pala y atizador desarmable"},
        {"sku": "BPPC01", "nombre": "Funda para parrilla plegable"},
    ])

    assert "parrilla plegable" in texto.lower()
    assert "Kit pala y atizador desarmable" in texto
    assert "Funda para parrilla plegable" in texto
    assert "te pasamos precio" in texto


def test_texto_cross_sell_parrillas_es_especifico():
    texto = _armar_texto_propuesta_cross_sell([
        {"sku": "KITPACH", "nombre": "Kit pala y atizador"},
        {"sku": "B4030H", "nombre": "Brasero 30x40"},
        {"sku": "B5030H", "nombre": "Brasero 30x53"},
    ])

    assert "esta parrilla" in texto.lower()
    assert "Kit pala y atizador" in texto
    assert "Brasero 30x40" in texto
    assert "Brasero 30x53" in texto
    assert "te pasamos precio" in texto            