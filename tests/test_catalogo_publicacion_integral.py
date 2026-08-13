from pathlib import Path

from services.catalogo_ficha_integral import (
    calcular_completitud,
    numero_visual,
    parsear_atributos,
    parsear_variantes,
)


def test_atributos_y_variantes_tienen_formato_controlado():
    assert parsear_atributos("Tamaño=60x40\nMaterial=Hierro") == {
        "Tamaño": "60x40", "Material": "Hierro",
    }
    assert parsear_variantes("PP-NEGRA | Color=Negro") == [{
        "sku": "PP-NEGRA", "opciones": "Color=Negro", "activa": True,
    }]


def test_presentacion_logistica_elimina_decimales_innecesarios():
    assert numero_visual("3000.000") == "3000"
    assert numero_visual("30.500") == "30.5"


def test_completitud_bloquea_fichas_incompletas():
    class Ficha:
        marca = categoria = descripcion_corta = descripcion_publica = None
        material = contenido_paquete = None
        imagenes_json = "[]"

    class Producto:
        peso_gr = largo_cm = ancho_cm = alto_cm = None

    porcentaje, faltantes = calcular_completitud(Ficha(), Producto())
    assert porcentaje == 0
    assert "imagen" in faltantes
    assert "peso embalado" in faltantes


def test_ficha_cubre_publicacion_logistica_variantes_y_cross_sell():
    modelo = Path("models/catalogo_producto.py").read_text(encoding="utf-8")
    servicio = Path("services/catalogos_admin_comercial.py").read_text(encoding="utf-8")
    plantilla = Path("templates/admin_comercial.html").read_text(encoding="utf-8")
    migraciones = Path("services/migraciones_saas.py").read_text(encoding="utf-8")
    for contrato in (
        "atributos_json", "variantes_json", "imagenes_json", "canales_json",
        "relaciones_json", "completitud_pct", "peso_producto_gr",
    ):
        assert contrato in modelo
        assert contrato in migraciones
    assert "subir_imagenes" in servicio
    assert "La ficha no puede quedar disponible" in servicio
    for texto in (
        "Producto y embalaje", "Atributos y variantes", "Imágenes",
        "Canales de publicación", "Cross-sell y relaciones", "Completitud actual",
    ):
        assert texto in plantilla
    assert "no publica ni sincroniza" in plantilla.lower()
