from pathlib import Path

import pytest

from services.catalogos_admin_comercial import (
    ESTADOS_COMERCIALES,
    ESTADOS_DISPONIBILIDAD,
    _decimal_opcional,
)


def leer(ruta):
    return Path(ruta).read_text(encoding="utf-8")


def test_estados_del_catalogo_separan_ciclo_y_disponibilidad():
    assert ESTADOS_COMERCIALES == {"borrador", "activo", "discontinuado"}
    assert ESTADOS_DISPONIBILIDAD == {
        "no_disponible", "disponible", "sin_stock", "pausado",
    }


def test_datos_fisicos_aceptan_decimal_argentino_y_rechazan_negativos():
    assert _decimal_opcional({"peso": "3200,50"}, "peso") == 3200.5
    assert _decimal_opcional({"peso": ""}, "peso") is None
    with pytest.raises(ValueError, match="no puede ser negativo"):
        _decimal_opcional({"peso": "-1"}, "peso")


def test_ficha_integral_es_aditiva_y_se_migra_en_el_arranque():
    modelo = leer("models/catalogo_producto.py")
    migraciones = leer("services/migraciones_saas.py")
    bootstrap = leer("services/bootstrap_base_datos.py")
    for campo in (
        "marca", "categoria", "descripcion_corta", "descripcion_publica",
        "estado_comercial", "estado_disponibilidad", "motivo_disponibilidad",
    ):
        assert campo in modelo
        assert f'"{campo}"' in migraciones
    assert "def asegurar_ficha_catalogo_integral" in migraciones
    assert "asegurar_ficha_catalogo_integral(" in bootstrap
    assert "UPDATE catalogo_producto SET estado_comercial" in migraciones


def test_gestion_integral_conserva_fuentes_separadas():
    servicio = leer("services/catalogos_admin_comercial.py")
    assert 'accion == "gestionar_producto_catalogo"' in servicio
    assert 'inclusion.estado_comercial = estado' in servicio
    assert 'inclusion.estado_disponibilidad = disponibilidad' in servicio
    assert 'producto.peso_gr = ' in servicio
    assert 'producto.permite_correo = ' in servicio
    assert "precio_centavos" not in servicio.split(
        'if accion == "gestionar_producto_catalogo":', 1
    )[1].split('if accion in {"activar_producto_catalogo"', 1)[0]


def test_interfaz_prioriza_tabla_filtros_y_modal_gestionable():
    plantilla = leer("templates/admin_comercial.html")
    javascript = leer("static/admin_comercial.js")
    estilos = leer("static/admin_comercial.css")
    assert "Configurar catálogos e incorporar productos" in plantilla
    assert 'id="catalog-product-search"' in plantilla
    assert "Productos del catálogo" in plantilla
    assert 'class="catalog-product-dialog"' in plantilla
    assert "Estado comercial" in plantilla
    assert "Datos físicos y reglas de envío" in plantilla
    assert "data-open-catalog-dialog" in javascript
    assert "filtrarCatalogo" in javascript
    assert ".catalog-product-dialog" in estilos


def test_producto_no_activo_no_puede_quedar_disponible():
    servicio = leer("services/catalogos_admin_comercial.py")
    bloque = servicio.split(
        'if accion == "gestionar_producto_catalogo":', 1
    )[1].split('if accion in {"activar_producto_catalogo"', 1)[0]
    assert 'if estado != "activo":' in bloque
    assert 'disponibilidad = "no_disponible"' in bloque
    assert 'disponibilidad in {"sin_stock", "pausado"}' in bloque
